# ONE-FILE launcher: creates two embedded Slurm batch scripts locally, uploads,
# submits the scanner array, waits for its dependent collector, downloads evidence.
# No Python, CodeQL, or repository analysis runs on the cluster login node.
$ErrorActionPreference = 'Stop'
$cluster = 'astrauss@146.141.21.100'
$remoteRoot = '/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2'
$workDir = Join-Path $env:TEMP ('phase2_historical_gate_' + [guid]::NewGuid().ToString('N'))
[void](New-Item -ItemType Directory -Path $workDir -Force)
$localScan = Join-Path $workDir 'historical_gate_16_17_batch.sbatch'
$localPack = Join-Path $workDir 'historical_gate_16_17_collect_batch.sbatch'
$utf8 = New-Object System.Text.UTF8Encoding($false)
$scanScript = @'
#!/bin/bash
#SBATCH --job-name=p2histgate
#SBATCH --partition=batch
#SBATCH --array=0-3%2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histgate_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histgate_%A_%a.err

# Frozen historical base/head CodeQL control. No analysis or Python on login node.
# Array tasks are independently isolated; no existing outputs are replaced.
set -euo pipefail
umask 077
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"

python3 - <<'PY'
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SPECS = (
    {
        'rank': 16, 'root_id': 'CROOT-00313-01', 'case_id': 313,
        'repo': 'gsd-build/gsd-2', 'pr': 3090,
        'base': 'fe0e218954d5e42d2045192f8b8234c0cd56b8c6',
        'head': '42b4470fbc2bbb4944ae5f3f36c99640b24efd06',
        'rule': 'js/polynomial-redos',
        'target_file': 'packages/pi-ai/src/utils/repair-tool-json.ts',
        'flow_files': ['packages/pi-ai/src/utils/repair-tool-json.ts'],
    },
    {
        'rank': 17, 'root_id': 'CROOT-10339-01', 'case_id': 10339,
        'repo': 'binaricat/Netcatty', 'pr': 2354,
        'base': 'ce3127c8c216003a5b022926ad3fd728ba9e9781',
        'head': '95ad7e90dfa3e6fccbfabc6bb3fb812feb1ab32c',
        'rule': 'js/clear-text-storage-of-sensitive-data',
        'target_file': 'infrastructure/persistence/localStorageAdapter.ts',
        'flow_files': ['application/defaultKeyPassphrases.ts',
                       'components/vault/useVaultImportHandlers.ts'],
    },
)

job = os.environ.get('SLURM_ARRAY_JOB_ID', '')
task = os.environ.get('SLURM_ARRAY_TASK_ID', '')
assert re.fullmatch(r'[0-9]+', job) and re.fullmatch(r'[0-3]', task), 'Must use Slurm array 0-3'
idx = int(task)
spec = SPECS[idx // 2]
arm = 'base' if idx % 2 == 0 else 'head'
commit = spec[arm]
root = Path.home() / 'research_artifacts' / 'prevention_pilot_phase2'
out = root / ('historical_gate_16_17_job' + job) / ('rank_' + str(spec['rank'])) / arm
out.mkdir(parents=True, exist_ok=False)
scratch_base = Path(os.environ.get('SLURM_TMPDIR') or '/tmp')
scratch = scratch_base / ('p2histgate_' + job + '_' + task)
scratch.mkdir(parents=True, exist_ok=False)
source = scratch / 'repo'
source.mkdir()

codeql = Path.home() / 'tools/codeql/codeql'
pack = Path.home() / '.codeql/packages/codeql/javascript-queries/2.3.11'
assert codeql.is_file() and pack.is_dir(), 'Missing pinned CodeQL executable or query pack'

def sha256_file(path):
    hasher = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1 << 20), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

report = {
    'protocol': 'phase2-frozen-issue-historical-base-head-exact-CodeQL-control-v1',
    'job_id': job, 'array_task': idx, 'case_rank': spec['rank'],
    'case_id': spec['case_id'], 'root_id': spec['root_id'],
    'repository': spec['repo'], 'pr_number': spec['pr'], 'arm': arm,
    'commit_sha': commit, 'historical_base_sha': spec['base'],
    'historical_head_sha': spec['head'], 'rule_id': spec['rule'],
    'target_file': spec['target_file'], 'changed_flow_files': spec['flow_files'],
    'scan_started_utc': now(), 'status': 'STARTED',
    'restriction': 'Researcher-only historical control; never use this to form O prompts'
}

def save():
    (out / 'RESULT.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

save()

try:
    if spec['rule'] == 'js/polynomial-redos':
        query = pack / 'Performance/PolynomialReDoS.ql'
        assert query.is_file(), 'Historical polynomial ReDoS query missing'
    else:
        queries = []
        for p in pack.rglob('*.ql'):
            try:
                if re.search(r'@id\s+' + re.escape(spec['rule']) + r'(?![\w-])', p.read_text(encoding='utf-8', errors='replace')):
                    queries.append(p)
            except OSError:
                continue
        assert len(queries) == 1, f'Expected exactly one query for {spec["rule"]}; got {[str(x) for x in queries]}'
        query = queries[0]

    report['query_path'] = str(query)
    report['query_sha256'] = sha256_file(query)
    report['codeql_binary_sha256'] = sha256_file(codeql)
    save()

    def run(args, label, timeout):
        logfile = out / (label + '.log')
        print('START', spec['rank'], arm, label, flush=True)
        with logfile.open('x') as log:
            completed = subprocess.run([str(a) for a in args], cwd=source,
                stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        report[label + '_exit_code'] = completed.returncode
        save()
        print('END', spec['rank'], arm, label, completed.returncode, flush=True)
        if completed.returncode:
            raise RuntimeError(f'{label} failed: exit {completed.returncode}; see {logfile}')

    archive = scratch / 'commit.tar.gz'
    url = f'https://codeload.github.com/{spec["repo"]}/tar.gz/{commit}'
    last_error = None
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent': 'Wits-Phase2-Historical-Gate-2026'})
            size = 0
            with urlopen(req, timeout=180) as upstream, archive.open('xb') as dest:
                while True:
                    block = upstream.read(1 << 20)
                    if not block:
                        break
                    size += len(block)
                    if size > 650_000_000:
                        raise RuntimeError('Download exceeds 650 MB safety limit')
                    dest.write(block)
            last_error = None
            break
        except Exception as exc:
            last_error = str(exc)
            archive.unlink(missing_ok=True)
            print('DOWNLOAD_RETRY', spec['rank'], arm, attempt + 1, last_error, flush=True)
            if attempt < 2:
                time.sleep(6 * (attempt + 1))
    if last_error is not None:
        raise RuntimeError('Historical commit archive unavailable: ' + last_error)
    report['archive_sha256'] = sha256_file(archive)
    report['archive_bytes'] = archive.stat().st_size
    save()

    nfiles = 0
    total_size = 0
    with tarfile.open(archive, 'r:gz') as bundle:
        for member in bundle:
            parts = pathlib.PurePosixPath(member.name).parts
            if len(parts) < 2:
                continue
            relative = pathlib.PurePosixPath(*parts[1:])
            if relative.is_absolute() or '..' in relative.parts:
                raise RuntimeError('Unsafe archive path')
            dest = source.joinpath(*relative.parts)
            if member.isdir():
                dest.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                nfiles += 1
                total_size += member.size
                if nfiles > 130_000 or total_size > 2_500_000_000:
                    raise RuntimeError('Archive exceeds file-count or extracted-byte cap')
                dest.parent.mkdir(parents=True, exist_ok=True)
                upstream = bundle.extractfile(member)
                if upstream is None:
                    raise RuntimeError('Missing archive member content')
                with upstream, dest.open('xb') as local:
                    while True:
                        chunk = upstream.read(1 << 20)
                        if not chunk:
                            break
                        local.write(chunk)
    report['extracted_files'] = nfiles
    report['extracted_bytes'] = total_size
    report['target_file_exists'] = (source / spec['target_file']).is_file()
    if report['target_file_exists']:
        report['target_file_sha256'] = sha256_file(source / spec['target_file'])
    elif arm == 'head':
        raise RuntimeError('Frozen expected head target file absent: ' + spec['target_file'])
    save()

    run([codeql, 'version'], 'codeql_version', 60)
    database = scratch / 'database'
    run([codeql, 'database', 'create', database,
        '--language=javascript-typescript', '--source-root=' + str(source),
        '--build-mode=none', '--threads=4', '--ram=19000'], 'database_create', 6000)
    sarif_path = out / 'target_rule.sarif'
    run([codeql, 'database', 'analyze', database, query,
        '--format=sarif-latest', '--output=' + str(sarif_path),
        '--threads=4', '--ram=19000'], 'target_query', 2400)

    sarif = json.loads(sarif_path.read_text(encoding='utf-8'))
    hits = []
    for execution in sarif.get('runs', []):
        for result in execution.get('results', []):
            if result.get('ruleId') != spec['rule']:
                continue
            locations = []
            for position in result.get('locations', []):
                physical = position.get('physicalLocation', {})
                locations.append({
                    'path': physical.get('artifactLocation', {}).get('uri', ''),
                    'line': physical.get('region', {}).get('startLine'),
                    'start_column': physical.get('region', {}).get('startColumn')})
            flows = []
            for codeflow in result.get('codeFlows', []):
                for thread in codeflow.get('threadFlows', []):
                    steps = []
                    for position in thread.get('locations', []):
                        loc = position.get('location', {})
                        phys = loc.get('physicalLocation', {})
                        steps.append({
                            'path': phys.get('artifactLocation', {}).get('uri', ''),
                            'line': phys.get('region', {}).get('startLine'),
                            'message': loc.get('message', {}).get('text', '')})
                    flows.append(steps)
            hits.append({
                'locations': locations,
                'message': result.get('message', {}).get('text'),
                'partialFingerprints': result.get('partialFingerprints', {}),
                'code_flows': flows})

    def touches_target(hit):
        return any(spec['target_file'] in str(p.get('path', ''))
            for p in hit['locations'])

    def touches_changed_flow(hit):
        for flow in hit['code_flows']:
            for step in flow:
                if any(f in str(step.get('path', '')) for f in spec['flow_files']):
                    return True
        return False

    report['total_rule_alerts'] = len(hits)
    report['target_file_alerts'] = [hit for hit in hits if touches_target(hit)]
    report['changed_flow_intersecting_alerts'] = [hit for hit in hits if touches_changed_flow(hit)]
    report['all_rule_alerts'] = hits
    report['status'] = 'SCAN_COMPLETE'
    report['scan_finished_utc'] = now()
    save()
    print('SCAN_COMPLETE', spec['rank'], arm, 'all_rule', len(hits),
        'target_file', len(report['target_file_alerts']),
        'flow', len(report['changed_flow_intersecting_alerts']), flush=True)
except Exception as exc:
    report['status'] = 'FAILED'
    report['failure_type'] = type(exc).__name__
    report['failure_message'] = str(exc)[:2000]
    report['scan_finished_utc'] = now()
    save()
    print('SCAN_FAILED', spec['rank'], arm, type(exc).__name__, str(exc), flush=True)
    traceback.print_exc()
    sys.exit(1)
PY
'@
$packScript = @'
#!/bin/bash
#SBATCH --job-name=p2histpack
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histpack_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/p2histpack_%j.err

# Slurm worker ONLY. Collects the four independent historical control outputs.
set -euo pipefail
umask 077
: "${GATE_JOBID:?Missing GATE_JOBID}"
[[ "$GATE_JOBID" =~ ^[0-9]+$ ]] || exit 2
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
DIR="historical_gate_16_17_job${GATE_JOBID}"
ARCHIVE="${ROOT}/${DIR}.tar.gz"
[ -d "${ROOT}/${DIR}" ] || { echo "MISSING_RESULTS_DIR ${DIR}"; exit 3; }
[ ! -e "$ARCHIVE" ] || { echo "REFUSE_OVERWRITE ${ARCHIVE}"; exit 4; }

# Include detailed SARIF and task logs; archive only this new Slurm array's outputs.
tar -czf "$ARCHIVE" -C "$ROOT" "$DIR"
sha256sum "$ARCHIVE"
ls -lh "$ARCHIVE"

# Task outcomes are published without hiding failures.
for rank in 16 17; do
  for arm in base head; do
    path="${ROOT}/${DIR}/rank_${rank}/${arm}/RESULT.json"
    if [ -f "$path" ]; then
      grep -m1 '"status"' "$path" || true
      grep -m1 '"total_rule_alerts"' "$path" || true
    else
      echo "MISSING_RESULT rank=${rank} arm=${arm}"
    fi
  done
done

echo "ARCHIVE_READY $ARCHIVE"
'@
# Unix line endings, UTF-8 without BOM: safe for #!/bin/bash on Slurm.
[System.IO.File]::WriteAllText($localScan, ($scanScript -replace "`r`n", "`n") + "`n", $utf8)
[System.IO.File]::WriteAllText($localPack, ($packScript -replace "`r`n", "`n") + "`n", $utf8)

$tag = (Get-Date -Format 'yyyyMMddHHmmss') + '_' + ([guid]::NewGuid().ToString('N').Substring(0,8))
$scanRemote = "historical_gate_16_17_${tag}_scan.sbatch"
$packRemote = "historical_gate_16_17_${tag}_pack.sbatch"

Write-Host '[1/4] Upload embedded Slurm jobs'
& scp.exe $localScan "${cluster}:${remoteRoot}/${scanRemote}"
if ($LASTEXITCODE -ne 0) { throw 'Scan script upload failed' }
& scp.exe $localPack "${cluster}:${remoteRoot}/${packRemote}"
if ($LASTEXITCODE -ne 0) { throw 'Collector script upload failed' }

Write-Host '[2/4] Submit scanner array on Slurm batch'
$scanResponse = & ssh.exe -o ServerAliveInterval=30 $cluster "sbatch --parsable --partition=batch ${remoteRoot}/${scanRemote}"
if ($LASTEXITCODE -ne 0) { throw "Scanner submission failed: $scanResponse" }
$scanText = ($scanResponse -join "`n").Trim()
$scanMatch = [regex]::Match($scanText, '(?m)^([0-9]+)(?:;[A-Za-z0-9_-]+)?$')
if (-not $scanMatch.Success) { throw "Could not extract Slurm job ID from: $scanText" }
$scanJob = $scanMatch.Groups[1].Value
Write-Host "SCAN_JOB=$scanJob"

Write-Host '[3/4] Submit dependent collector; waiting for completion'
$packResponse = & ssh.exe -o ServerAliveInterval=30 $cluster "sbatch --wait --parsable --partition=batch --dependency=afterany:${scanJob} --export=ALL,GATE_JOBID=${scanJob} ${remoteRoot}/${packRemote}"
$packExit = $LASTEXITCODE
$packText = ($packResponse -join "`n").Trim()
Write-Host "Collector response: $packText"
if ($packExit -ne 0) {
    Write-Warning 'Collector returned nonzero or connection was interrupted; attempting archive download.'
}

Write-Host '[4/4] Download the complete historical scan evidence'
$archive = "historical_gate_16_17_job${scanJob}.tar.gz"
$destination = Join-Path $PSScriptRoot $archive
& scp.exe "${cluster}:${remoteRoot}/${archive}" $destination
if ($LASTEXITCODE -ne 0) {
    Write-Warning 'Archive download failed. Retrieving Slurm state and logs.'
    & ssh.exe $cluster "sacct -j ${scanJob} -X -P -o JobID,JobName,State,ExitCode,Elapsed"
    foreach ($i in 0..3) {
        foreach ($ext in @('out','err')) {
            $name = "p2histgate_${scanJob}_${i}.${ext}"
            & scp.exe -q "${cluster}:${remoteRoot}/${name}" (Join-Path $PSScriptRoot $name) 2>$null
        }
    }
    throw "Archive not ready. SCAN_JOB=$scanJob. Upload downloaded p2histgate logs."
}
if (-not (Test-Path -LiteralPath $destination)) { throw "Missing local archive: $destination" }
Write-Host "DONE: $destination"
Write-Host 'Upload the .tar.gz to ChatGPT.'
