#!/usr/bin/env python3
"""Independent O/W/P coding-agent runs from frozen research packets.

Dependencies: Python 3.10+, git, and authenticated OpenAI Codex CLI.
Never uses existing O/W/P patches as examples. Never mutates input ZIPs.
Run --help and --dry-run first. --execute is required for LLM calls.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import time
import zipfile

ARMS = ("O", "W", "P")
MAX_FILES = 60000
MAX_UNCOMPRESSED = 3 * 1024**3
MAX_DIFF_BYTES = 20 * 1024**2
PROMPT_WRAPPER = """You are in a new, independent software-implementation experiment.
You are working inside the frozen source repository given to you.
Use ONLY the repository files plus the original issue/instructions supplied below.
Do not consult GitHub, earlier commits, historical PRs, previous chats, or network sources.
Do not run CodeQL or seek other security-warning feedback.
Implement the requested functionality as completely as reasonably possible.
You may add targeted tests if useful. Do not alter files outside this repository.
Do not create an output patch yourself: the experiment runner captures the git diff.
Do not change the research condition or add requirements not present in the issue.
Report accurately what was done and which commands/tests were actually run.

======= RUN_INSTRUCTIONS.md =======
{run_instructions}

======= ISSUE.md =======
{issue}
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(2 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run_cmd(args: list[str], cwd: Path, *, timeout=180, stdin=None):
    return subprocess.run(args, cwd=str(cwd), input=stdin, capture_output=True,
                          text=True, timeout=timeout, check=False)


def save_json(path: Path, obj: dict):
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def load_index(packet_dir: Path):
    path = packet_dir / 'PACKET_INDEX.csv'
    if not path.exists():
        raise RuntimeError(f'Missing frozen manifest: {path}')
    with path.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    names = set()
    for item in rows:
        case = int(item['case_id'])
        arm = item['arm']
        if arm not in ARMS or (case, arm) in names:
            raise RuntimeError(f'Bad/duplicate experimental arm: {case}/{arm}')
        names.add((case, arm))
        filename = f'CASE_{case:05d}_{arm}.zip'
        if item['filename'] != filename:
            raise RuntimeError(f'Incorrect filename for {case}/{arm}')
        if (packet_dir / filename).stat().st_size != int(item['bytes']):
            raise RuntimeError(f'Frozen archive length mismatch: {filename}')
        if sha256_file(packet_dir / filename) != item['sha256']:
            raise RuntimeError(f'Frozen archive SHA256 mismatch: {filename}')
    if len(names) != 42 or len({c for c, _ in names}) != 14:
        raise RuntimeError(f'Expected 14 cases x 3 conditions; found {len(names)} packets')
    return { (int(i['case_id']), i['arm']): i for i in rows }


def safe_extract(packet: Path, destination: Path):
    """Strict archive extraction; this raises rather than guessing how to handle symlinks."""
    uncompressed = 0
    file_count = 0
    issue = None
    instructions = None
    with zipfile.ZipFile(packet) as archive:
        if archive.testzip() is not None:
            raise RuntimeError('Corrupt ZIP file')
        seen = set()
        for info in archive.infolist():
            raw_name = info.filename
            if '\\' in raw_name or ':' in raw_name or raw_name.startswith('/'):
                raise RuntimeError(f'Unsafe ZIP entry: {raw_name}')
            parts = PurePosixPath(raw_name).parts
            if not parts or '..' in parts or '.' in parts or any(x in ('', '.git') for x in parts):
                raise RuntimeError(f'Unsafe ZIP path: {raw_name}')
            if info.is_dir():
                continue
            if raw_name in seen:
                raise RuntimeError(f'Duplicate ZIP path: {raw_name}')
            seen.add(raw_name)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise RuntimeError(f'Symlink in source ZIP needs explicit provenance review: {raw_name}')
            uncompressed += info.file_size
            file_count += 1
            if uncompressed > MAX_UNCOMPRESSED or file_count > MAX_FILES:
                raise RuntimeError('Oversized archive; ask for a targeted handling procedure')
            if raw_name == 'ISSUE.md':
                issue = archive.read(info).decode('utf-8')
            elif raw_name == 'RUN_INSTRUCTIONS.md':
                instructions = archive.read(info).decode('utf-8')
            elif raw_name.startswith('REPO/'):
                rel = parts[1:]
                if not rel:
                    continue
                file_path = destination.joinpath(*rel)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, file_path.open('wb') as dst:
                    shutil.copyfileobj(src, dst)
                # Preserve executable permission where present (relevant for shell projects).
                if os.name != 'nt' and mode & stat.S_IXUSR:
                    file_path.chmod(file_path.stat().st_mode | stat.S_IXUSR)
            else:
                raise RuntimeError(f'Unexpected ZIP file outside REPO/: {raw_name}')
    if not issue or not instructions:
        raise RuntimeError('Packet lacks ISSUE.md or RUN_INSTRUCTIONS.md')
    return issue, instructions, file_count - 2


def initialize_repo(repo: Path):
    sequence = [
        ['git', 'init', '-q', '--initial-branch=main'],
        ['git', '-c', 'core.autocrlf=false', 'add', '-f', '--all'],
        ['git', '-c', 'user.name=OWP Research', '-c', 'user.email=owp-research@localhost',
         '-c', 'commit.gpgsign=false', 'commit', '--quiet', '--allow-empty', '-m', 'Frozen case baseline'],
    ]
    for command in sequence:
        proc = run_cmd(command, repo, timeout=900)
        if proc.returncode:
            raise RuntimeError(f'Git baseline failed: {command}: {proc.stderr[-1000:]}')
    head = run_cmd(['git', 'rev-parse', 'HEAD'], repo)
    if head.returncode:
        raise RuntimeError('Git baseline HEAD cannot be resolved')
    return head.stdout.strip()


def capture_patch(repo: Path, target: Path):
    add = run_cmd(['git', '-c', 'core.autocrlf=false', 'add', '-f', '--all'], repo, timeout=300)
    if add.returncode:
        raise RuntimeError(f'Unable to stage generated changes: {add.stderr[-600:]}')
    res = subprocess.run(['git', '--no-pager', '-c', 'core.autocrlf=false', 'diff', '--cached',
                          '--binary', '--no-ext-diff', '--no-color', 'HEAD', '--'],
                         cwd=str(repo), capture_output=True, timeout=400)
    if res.returncode:
        raise RuntimeError(f'Unable to generate diff: {res.stderr[-600:]}')
    target.write_bytes(res.stdout)
    if len(res.stdout) > MAX_DIFF_BYTES:
        return 'OVERSIZED_PATCH'
    return 'PATCH' if res.stdout else 'NO_PATCH'


def call_codex(codex_cmd: str, repo: Path, model: str, prompt: str, run_dir: Path, minutes: int):
    command = [codex_cmd, 'exec', '--ephemeral', '--ignore-user-config', '--ignore-rules',
               '--sandbox', 'workspace-write', '--model', model,
               '-C', str(repo), '--json', '-']
    (run_dir / 'codex_command.json').write_text(
        json.dumps({'args': command[:-1] + ['<ISSUE_FROM_FROZEN_PACKET_ON_STDIN>']}, indent=2) + '\n',
        encoding='utf-8')
    stdout_path = run_dir / 'codex_events.jsonl'
    stderr_path = run_dir / 'codex_stderr.log'
    started = time.monotonic()
    status = 'CODEX_ERROR'
    returncode = None
    with stdout_path.open('wb') as stdout, stderr_path.open('wb') as stderr:
        proc = subprocess.Popen(command, cwd=str(repo), stdin=subprocess.PIPE,
                                stdout=stdout, stderr=stderr)
        try:
            proc.communicate(input=prompt.encode('utf-8'), timeout=minutes * 60)
            returncode = proc.returncode
            status = 'CODEX_OK' if returncode == 0 else 'CODEX_ERROR'
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            status = 'TIMEOUT'
            returncode = 124
    return {'codex_status': status, 'codex_exit_code': returncode,
            'elapsed_seconds': round(time.monotonic() - started, 1),
            'codex_events_file': stdout_path.name, 'codex_stderr_file': stderr_path.name}


def run_one(spec, args, index):
    cid, arm, rep = spec
    label = f'CASE_{cid:05d}_{arm}_r{rep:02d}'
    run_dir = args.out / 'runs' / label
    if run_dir.exists():
        old_result = run_dir / 'result.json'
        prior = json.loads(old_result.read_text(encoding='utf-8')) if old_result.exists() else {}
        return {'run': label, 'status': prior.get('status', 'PRESERVED_INCOMPLETE'),
                'preserved_existing': True,
                'note': 'Never overwrite; inspect existing run or use a new replication number'}
    run_dir.mkdir(parents=True)
    repo = run_dir / 'worktree'
    repo.mkdir()
    record = {
        'case_id': cid, 'arm': arm, 'replication': rep,
        'model': args.model, 'agent': 'OpenAI Codex CLI',
        'sandbox': 'workspace-write', 'ephemeral': True,
        'issue_provenance': 'HISTORICAL_ISSUE_BODY_ASOF_PR_UNVERIFIED',
        'source_mode': index[(cid, arm)]['source_type'],
        'input_zip_sha256': index[(cid, arm)]['sha256'],
        'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'status': 'PREPARING',
    }
    record_path = run_dir / 'result.json'
    save_json(record_path, record)
    try:
        packet = args.packets / index[(cid, arm)]['filename']
        issue, instructions, number_files = safe_extract(packet, repo)
        record['repo_files'] = number_files
        record['task_prompt_sha256'] = hashlib.sha256(
            PROMPT_WRAPPER.format(run_instructions=instructions, issue=issue).encode('utf-8')).hexdigest()
        record['git_baseline_commit'] = initialize_repo(repo)
        record['status'] = 'GENERATING'
        save_json(record_path, record)
        record.update(call_codex(args.codex, repo, args.model,
                   PROMPT_WRAPPER.format(run_instructions=instructions, issue=issue),
                   run_dir, args.max_minutes))
        patch = run_dir / f'{label}.patch'
        patch_kind = capture_patch(repo, patch)
        record['patch_sha256'] = sha256_file(patch)
        record['patch_bytes'] = patch.stat().st_size
        record['patch_file'] = patch.name
        record['status'] = (
            'NO_PATCH' if patch_kind == 'NO_PATCH'
            else 'OVERSIZED_PATCH' if patch_kind == 'OVERSIZED_PATCH'
            else 'GENERATED_UNTESTED' if record['codex_status'] == 'CODEX_OK'
            else 'PARTIAL_OR_FAILED_WITH_PATCH')
    except Exception as exc:
        record['status'] = 'RUNNER_ERROR'
        record['error'] = f'{type(exc).__name__}: {exc}'[:1600]
        # Attempt capture of partial code; retain agent failures rather than silently rerunning.
        if (repo / '.git').exists():
            try:
                partial = run_dir / f'{label}.patch'
                capture_patch(repo, partial)
                record['patch_file'] = partial.name
                record['patch_sha256'] = sha256_file(partial)
                record['patch_bytes'] = partial.stat().st_size
            except Exception as secondary:
                record['partial_capture_error'] = str(secondary)[:500]
    finally:
        record['ended_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
        save_json(record_path, record)
        if not args.keep_worktrees and repo.exists():
            shutil.rmtree(repo)
    return {'run': label, 'status': record['status'],
            'patch_bytes': record.get('patch_bytes', 0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packets', type=Path, required=True,
                        help='Directory downloaded from the frozen 42 ZIPs')
    parser.add_argument('--out', type=Path, required=True,
                        help='New output directory for independently generated patches')
    parser.add_argument('--model', required=True,
                        help='One fixed Codex model string for all arms and cases')
    parser.add_argument('--cases', default='all',
                        help='Comma-separated case IDs, or all (default)')
    parser.add_argument('--arms', default='O,W,P',
                        help='Comma-separated arms (default O,W,P)')
    parser.add_argument('--replications', type=int, default=1,
                        help='Replications per arm, each in a fresh session')
    parser.add_argument('--start-rep', type=int, default=1)
    parser.add_argument('--max-minutes', type=int, default=35)
    parser.add_argument('--max-runs', type=int, default=0,
                        help='For a small initial pilot, e.g. 3 (0 = all)')
    parser.add_argument('--codex', default='codex',
                        help='Codex executable (default: codex on PATH)')
    parser.add_argument('--execute', action='store_true',
                        help='Actually invoke agent. Without this flag, dry-run only.')
    parser.add_argument('--keep-worktrees', action='store_true',
                        help='Keep extracted repositories (uses substantial disk)')
    args = parser.parse_args()
    if args.replications <= 0 or args.start_rep <= 0 or not (1 <= args.max_minutes <= 240):
        parser.error('Invalid repetitions/start repetition/timeout')
    args.packets = args.packets.expanduser().resolve()
    args.out = args.out.expanduser().resolve()
    if args.packets == args.out or args.out.is_relative_to(args.packets):
        parser.error('Output directory cannot be inside the frozen packet directory')
    index = load_index(args.packets)
    cases = sorted({c for c, _ in index}) if args.cases == 'all' else sorted(set(int(c) for c in args.cases.split(',')))
    arms = [a.strip().upper() for a in args.arms.split(',')]
    if not arms or len(set(arms)) != len(arms) or any(a not in ARMS for a in arms):
        parser.error('Specify unique arms from O,W,P')
    arms = sorted(arms, key=lambda a: ARMS.index(a))
    selected = [(cid, arm, rep)
                for rep in range(args.start_rep, args.start_rep + args.replications)
                for cid in cases for arm in arms]
    if any((cid, arm) not in index for cid, arm, _ in selected):
        parser.error('One or more selected cases / conditions do not exist')
    if args.max_runs:
        selected = selected[:args.max_runs]
    print(f'Preflight PASS: 42 valid frozen ZIPs; selected: {len(selected)} new sessions')
    print(f'Model: {args.model}; sandbox: workspace-write; independent ephemeral sessions')
    print('IMPORTANT: Codex CLI runs may consume plan quota or incur API charges, depending on auth.')
    print('Selected:', ', '.join(f'{c}/{a}/r{r:02d}' for c, a, r in selected))
    if not args.execute:
        print('\nDRY RUN COMPLETE. Add --execute to run the selected agents.')
        return 0
    executable = shutil.which(args.codex) or (args.codex if Path(args.codex).is_file() else None)
    if not executable:
        parser.error('Codex CLI not found. Install and sign in before using --execute.')
    check = run_cmd([executable, '--version'], Path.cwd())
    if check.returncode:
        parser.error(f'Codex CLI unavailable: {check.stderr[-500:]}')
    args.codex = executable
    args.out.mkdir(parents=True, exist_ok=True)
    manifest_path = args.out / 'RUNNER_MANIFEST.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('model') != args.model:
            parser.error('This output folder belongs to a different model; use a fresh --out')
    else:
        manifest = {'created_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
                    'model': args.model, 'codex_version': check.stdout.strip(),
                    'input_manifest_sha256': sha256_file(args.packets / 'PACKET_INDEX.csv'),
                    'source': 'frozen_14_case_OWP_inputs',
                    'control_conditions': ARMS, 'runs': [],
                    'limitations': [
                      'Historical issue-body versions are unverified as of original PR',
                      'Four cases use filtered source snapshots',
                      'Task-specific acceptance is not automatically established by this generator',
                      'This is a NEW model cohort; do not pool with prior ChatGPT-web 668 attempts',
                    ]}
    for k, spec in enumerate(selected, 1):
        print(f'[{k}/{len(selected)}] {spec[0]:05d}/{spec[1]}/r{spec[2]:02d}', flush=True)
        result = run_one(spec, args, index)
        if not result.get('preserved_existing'):
            if any(item.get('run') == result['run'] for item in manifest['runs']):
                raise RuntimeError('Duplicate run identity in manifest: ' + result['run'])
            manifest['runs'].append(result)
            save_json(manifest_path, manifest)
        print('  ->', result['status'], flush=True)
    # Compact export: source code and agent logs excluded; user can upload this ZIP for cluster evaluation.
    round_label = f'r{args.start_rep:02d}-{args.start_rep + args.replications - 1:02d}'
    dest = args.out / f'PATCHES_{round_label}_{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}.zip'
    with zipfile.ZipFile(dest, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(manifest_path, 'RUNNER_MANIFEST.json')
        for item in sorted((args.out / 'runs').iterdir()):
            if not item.is_dir():
                continue
            for f in [item / 'result.json', *item.glob('CASE_*.patch')]:
                if f.exists():
                    z.write(f, 'runs/' + item.name + '/' + f.name)
    print('\nPATCH EXPORT:', dest)
    print('Upload this ZIP in the research chat for the standardized HPC evaluator.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
