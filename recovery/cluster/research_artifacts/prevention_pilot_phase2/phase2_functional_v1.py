#!/usr/bin/env python3
"""Non-destructive functional-test diagnostics for frozen prevention pilot baseline patches.

Automated tests are supporting evidence, not a substitute for human functional review.
Runs each patch against a freshly extracted, hash-verified frozen pre-PR archive.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

ROOT = Path(os.environ.get('PHASE2_ROOT', Path.home() / 'research_artifacts/prevention_pilot_phase2'))
OUT = ROOT / 'phase2_functional_results_v1'
TMP = Path(os.environ.get('SLURM_TMPDIR', f'/tmp/{os.environ.get("USER", "astrauss")}/phase2_func_v1')) / f'job_{os.environ.get("SLURM_JOB_ID", "manual")}'
BASES = {
    '3504': ('8541b55efc3ce1b5e0c52ada59f28fde410fdd0f5538af46378b1611eb2fdf55', 'pnpm'),
    '10819': ('ac15a6dd5c7eb6f2950246ee4b6fca59ee76d933624d26f7bfc4fb03952d99e6', 'npm'),
    '629': ('6c14fed117104182c4945e69eb5325855b482bc60f9b8571148f743a99aac223', 'npm'),
}
FIELDS = ('run_id','case','archive_sha256','patch_sha256','apply_status','install_status','compile_status','test_status','test_command','notes')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def restricted_env():
    # Do not pass the miner's GitHub/API credentials to third-party npm packages or patch tests.
    allow = {'PATH','HOME','USER','LOGNAME','LANG','LC_ALL','LC_CTYPE','TERM',
             'TMPDIR','TMP','TEMP','SLURM_TMPDIR','XDG_CACHE_HOME',
             'COREPACK_HOME','PNPM_HOME','NPM_CONFIG_CACHE','npm_config_cache',
             'NODE_EXTRA_CA_CERTS','SSL_CERT_FILE','SSL_CERT_DIR'}
    e = {k: v for k, v in os.environ.items() if k in allow}
    e.update({'CI': 'true', 'COREPACK_ENABLE_DOWNLOAD_PROMPT': '0',
              'COREPACK_ENABLE_AUTO_PIN': '0', 'npm_config_audit': 'false',
              'npm_config_fund': 'false', 'GIT_TERMINAL_PROMPT': '0'})
    return e


def log(msg):
    print(msg, flush=True)


def run(cmd, cwd, logfile, timeout=1800):
    log('RUN ' + ' '.join(cmd) + ' => ' + str(logfile))
    start = time.time()
    with open(logfile, 'w', encoding='utf-8') as f:
        f.write('$ ' + ' '.join(cmd) + '\n')
        f.flush()
        try:
            p = subprocess.run(cmd, cwd=cwd, env=restricted_env(), stdout=f,
                               stderr=subprocess.STDOUT, timeout=timeout, check=False)
            rc = p.returncode
            status = 'PASS' if rc == 0 else 'FAIL_RC_' + str(rc)
        except subprocess.TimeoutExpired:
            status = 'TIMEOUT'
        except (OSError, ValueError) as ex:
            f.write('\nEXEC_ERROR: ' + repr(ex) + '\n')
            status = 'EXEC_ERROR'
        f.write(f'\nSTATUS={status} ELAPSED={time.time()-start:.1f}s\n')
    return status


def extract(archive, dest):
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, 'r:gz') as t:
        t.extractall(dest, filter='data')


def checkpoint(case, records):
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f'CASE_{case}_FUNCTIONAL.csv'
    tmp = target.with_suffix('.tmp')
    with open(tmp, 'w', newline='', encoding='utf-8') as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(records)
    os.replace(tmp, target)
    log('CHECKPOINT ' + str(target) + ' rows=' + str(len(records)))


def test_steps(case, run_id):
    if case == '3504':
        # Root pnpm workspace; local @t3tools/web unit project.
        return (
            ['corepack', 'pnpm', 'install', '--frozen-lockfile', '--prefer-offline'],
            None,
            ['corepack', 'pnpm', '--filter', '@t3tools/web', 'exec', 'vp',
             'test', 'run', '--project', 'unit', 'src/components/ComposerPromptEditor.test.ts'],
        )
    if case == '10819':
        return (
            ['npm', 'ci', '--prefer-offline', '--no-audit', '--no-fund'],
            ['npm', 'run', 'test-compile'],
            ['npm', 'test', '--', '--runInBand', '--runTestsByPath',
             'src/test/UnitTests/RevealServer.jest.ts',
             'src/test/UnitTests/RevealContext.jest.ts',
             'src/test/UnitTests/FrontmatterDiagnostics.jest.ts'],
        )
    paths = ['src/bot/song-ref.test.ts']
    if run_id.endswith('R1'):
        paths.append('src/music/spotify.test.ts')
    return (
        ['npm', 'ci', '--prefer-offline', '--no-audit', '--no-fund'],
        ['npm', 'exec', '--no', '--', 'tsc', '--noEmit'],
        ['npm', 'test', '--', *paths],
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--case', choices=BASES, required=True)
    args = ap.parse_args()
    case = args.case
    archive = ROOT / 'repos' / f'O{case}_prePR.tar.gz'
    expected, _ = BASES[case]
    actual = sha256(archive)
    if actual != expected:
        raise RuntimeError(f'BASE ARCHIVE SHA MISMATCH for case {case}: {actual} != {expected}')
    log(f'CASE {case} ARCHIVE_VERIFIED {actual}')
    log(f'PYTHON {sys.executable} NODE via PATH {shutil.which("node")} NPM {shutil.which("npm")}')
    records = []
    for suffix in ('R1', 'R2'):
        run_id = f'O{case}_{suffix}'
        patch = ROOT / 'generated' / f'{run_id}.patch'
        patch_hash = sha256(patch)
        work = TMP / run_id
        if work.exists():
            shutil.rmtree(work)
        log(f'EXTRACT {run_id}')
        extract(archive, work)
        row = dict(run_id=run_id, case=case, archive_sha256=actual,
                   patch_sha256=patch_hash, apply_status='NOT_RUN',
                   install_status='NOT_RUN', compile_status='NOT_RUN',
                   test_status='NOT_RUN', test_command='', notes='')
        apply_status = run(['git', 'apply', '--check', str(patch)], work,
                           OUT / f'{run_id}_apply.log', timeout=60)
        if apply_status != 'PASS':
            row['apply_status'] = 'FAIL'
            row['notes'] = 'Frozen patch does not apply: see apply log. Not a test failure.'
            records.append(row)
            checkpoint(case, records)
            continue
        row['apply_status'] = 'OK'
        apply_status = run(['git', 'apply', str(patch)], work,
                           OUT / f'{run_id}_apply_actual.log', timeout=60)
        if apply_status != 'PASS':
            row['apply_status'] = 'FAIL'
            row['notes'] = 'Unexpected git apply failure: see log.'
            records.append(row)
            checkpoint(case, records)
            continue
        install, compile_step, test = test_steps(case, run_id)
        row['test_command'] = ' '.join(test)
        row['install_status'] = run(install, work, OUT / f'{run_id}_install.log', timeout=2400)
        if row['install_status'] != 'PASS':
            row['notes'] = 'DEPENDENCY_BLOCKED: installation failed/timed out; functionality UNKNOWN.'
            records.append(row)
            checkpoint(case, records)
            continue
        if compile_step:
            row['compile_status'] = run(compile_step, work,
                                        OUT / f'{run_id}_compile.log', timeout=1200)
        else:
            row['compile_status'] = 'NOT_APPLICABLE'
        row['test_status'] = run(test, work, OUT / f'{run_id}_test.log', timeout=1800)
        row['notes'] = 'Automated test outcome only; human issue-satisfaction review still required.'
        records.append(row)
        checkpoint(case, records)
    log(f'CASE_COMPLETE {case}')


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    main()
