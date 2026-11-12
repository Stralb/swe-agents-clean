#!/bin/bash
#SBATCH --job-name=case3882check
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=20G
#SBATCH --time=00:35:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_check_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/prevention_pilot_phase2/case3882_check_%j.err
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/tools/codeql:$PATH"
python3 - <<'PY'
import hashlib
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.request

root = pathlib.Path.home() / 'research_artifacts' / 'prevention_pilot_phase2'
job = os.environ['SLURM_JOB_ID']
out = root / ('case3882_historical_prescan_v2_job' + job)
# A preceding action may have already made the empty output directory.
# Never overwrite a nonempty directory or any prior result.
out.mkdir(parents=True, exist_ok=True)
assert not any(out.iterdir()), 'Output directory nonempty; refusing to overwrite'
scratch = pathlib.Path(os.environ.get('SLURM_TMPDIR') or '/tmp') / ('case3882_prescan_v2_' + job)
scratch.mkdir(parents=True, exist_ok=False)
base = '5789f89a3f6bed8a9f40447a73e75b81b277b1c8'
head = 'c53cfcd19d46d23f621c60dcc4d074814d417a59'
source_file = 'packages/api/src/artifacts/update.ts'
repository = 'LibreChat-AI/LibreChat'
codeql = pathlib.Path.home() / 'tools/codeql/codeql'
pack = pathlib.Path.home() / '.codeql/packages/codeql/javascript-queries/2.3.11'
rule = 'js/polynomial-redos'
assert codeql.is_file() and pack.is_dir(), 'CodeQL or pinned query pack missing'
queries = []
for file in pack.rglob('*.ql'):
    try:
        header = file.read_text(errors='replace')[:6000]
    except OSError:
        continue
    if re.search(r'(?m)^\s*\*?\s*@id\s+' + re.escape(rule) + r'\s*$', header):
        queries.append(file)
assert len(queries) == 1, 'Expected exactly one pinned CodeQL query; got ' + str(queries)
query = queries[0]
report = {
    'case_id': 3882,
    'historical_pr': 14121,
    'repository': repository,
    'rule': rule,
    'target_file': source_file,
    'base_sha': base,
    'head_sha': head,
    'query': str(query),
    'scope': 'Single-target-file historical preflight only; a negative result requires full-repo confirmation',
    'results': {}
}

def fetch(sha):
    url = 'https://raw.githubusercontent.com/' + repository + '/' + sha + '/' + source_file
    request = urllib.request.Request(url, headers={'User-Agent': 'Wits-case3882-prescan-v2'})
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(2_500_001)
            assert len(data) < 2_500_001, 'File too large'
            return data
        except Exception as exc:
            last_error = exc
            time.sleep(2)
    raise RuntimeError('Historical file fetch failed: ' + repr(last_error))

for name, sha in [('before', base), ('historical_pr', head)]:
    source_root = scratch / name
    dest = source_root / source_file
    dest.parent.mkdir(parents=True, exist_ok=True)
    code = fetch(sha)
    dest.write_bytes(code)
    result = report['results'][name] = {
        'source_sha256': hashlib.sha256(code).hexdigest(),
        'source_bytes': len(code),
        'target_line_217': code.decode('utf-8', errors='replace').splitlines()[216]
             if len(code.splitlines()) >= 217 else None,
    }
    db = scratch / ('db_' + name)
    sarif_path = out / (name + '.sarif')
    commands = [
        ('create', [codeql, 'database', 'create', db,
                    '--language=javascript-typescript',
                    '--source-root=' + str(source_root),
                    '--build-mode=none', '--threads=4', '--ram=15000']),
        ('analyze', [codeql, 'database', 'analyze', db, query,
                     '--format=sarif-latest', '--output=' + str(sarif_path),
                     '--threads=4', '--ram=15000']),
    ]
    for stage, cmd in commands:
        process = subprocess.run(
            [str(x) for x in cmd], cwd=source_root,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors='replace', timeout=1100
        )
        (out / (name + '_' + stage + '.log')).write_text(process.stdout)
        result[stage + '_exit'] = process.returncode
        print(name, stage, 'exit', process.returncode, flush=True)
        if process.returncode:
            raise RuntimeError(name + ' ' + stage + ' failed: ' + process.stdout[-700:])
    sarif = json.loads(sarif_path.read_text())
    hits = []
    for run in sarif.get('runs', []):
        for item in run.get('results', []):
            if item.get('ruleId') != rule:
                continue
            locations = []
            for loc in item.get('locations', []):
                physical = loc.get('physicalLocation', {})
                locations.append({
                    'file': physical.get('artifactLocation', {}).get('uri'),
                    'line': physical.get('region', {}).get('startLine'),
                })
            hits.append({
                'locations': locations,
                'fingerprints': item.get('partialFingerprints', {}),
            })
    result['target_alert_count'] = len(hits)
    result['target_alerts'] = hits

before_hits = report['results']['before']['target_alerts']
head_hits = report['results']['historical_pr']['target_alerts']
def key(hit):
    return json.dumps(hit['fingerprints'] or hit['locations'], sort_keys=True)
prior_keys = {key(hit) for hit in before_hits}
report['historical_pr_new_target_alerts'] = [hit for hit in head_hits if key(hit) not in prior_keys]
report['historical_pr_new_target_alert_count'] = len(report['historical_pr_new_target_alerts'])
report['preflight_verdict'] = (
    'PROMISING_NEW_HISTORICAL_RULE_FINDING' if report['historical_pr_new_target_alert_count']
    else 'NO_NEW_FINDING_IN_SINGLE_FILE_SCAN_REQUIRES_FULL_REPO_CHECK'
)
(out / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
print('COMPLETE', report['preflight_verdict'], flush=True)
print('BEFORE', len(before_hits), 'HEAD', len(head_hits), 'NEW', report['historical_pr_new_target_alert_count'], flush=True)
PY
