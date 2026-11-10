#!/bin/bash
#SBATCH --job-name=cf_diag3581
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_diag_3581/summary.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_diag_3581/summary.err

set -euo pipefail

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
ART="$MINER/data/distributed_spool/codeql_security/results/imported/scanner-job-600723.json"
WORKER="codeql-6084-0-mscluster106.ms.wits.ac.za-155786"
HB="$MINER/data/distributed_spool/codeql_security/heartbeats/${WORKER}.json"
CODEQL="$HOME/tools/codeql/codeql"
PACK="$HOME/.codeql/packages/codeql/javascript-queries/2.3.11"
DB="$MINER/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"

printf '=== FIXED INPUTS ===\n'
printf 'artifact=%s\n' "$ART"
printf 'worker_heartbeat=%s\n' "$HB"
printf 'current_codeql=%s\n' "$CODEQL"
printf 'query_pack=%s\n' "$PACK"

printf '\n=== CURRENT TOOLCHAIN ===\n'
"$CODEQL" version | head -4
printf 'codeql_sha256='; sha256sum "$CODEQL" | awk '{print $1}'
printf 'manifest_sha256='; sha256sum "$HOME/tools/codeql/.codeqlmanifest.json" | awk '{print $1}'
printf 'pack_lock_sha256='; sha256sum "$PACK/codeql-pack.lock.yml" | awk '{print $1}'
printf 'FileSystemRace_sha256='; sha256sum "$PACK/Security/CWE-367/FileSystemRace.ql" | awk '{print $1}'
printf 'MissingOriginCheck_sha256='; sha256sum "$PACK/Security/CWE-020/MissingOriginCheck.ql" | awk '{print $1}'

printf '\n=== ORIGINAL RESULT ARTIFACT ===\n'
test -f "$ART" || { echo 'ERROR: original artifact missing'; exit 2; }
printf 'artifact_sha256='; sha256sum "$ART" | awk '{print $1}'
python3 - "$ART" <<'PY'
import json,sys,re
p=sys.argv[1]
x=json.load(open(p,encoding='utf-8'))

print('top_keys=', sorted(x.keys()))

def walk(obj,path=''):
    if isinstance(obj,dict):
        for k,v in obj.items():
            np=f'{path}.{k}' if path else k
            kl=k.lower()
            if any(t in kl for t in ('case','job','worker','repo','sha','commit','scanner','language','suite','query','version','codeql','status')):
                if not isinstance(v,(dict,list)):
                    s=str(v).replace('\n','\\n')
                    if len(s)>500: s=s[:500]+'...'
                    print(f'{np}={s}')
            walk(v,np)
    elif isinstance(obj,list):
        for i,v in enumerate(obj): walk(v,f'{path}[{i}]')
walk(x)

# Pull out findings and runs compactly.
res=x.get('result',x)
print('\nORIGINAL_FINDINGS:')
for f in res.get('findings',[]) or []:
    rid=f.get('rule_id') or f.get('ruleId')
    if rid in {'js/file-system-race','js/missing-origin-check'}:
        print(json.dumps({k:f.get(k) for k in ('scanner','rule_id','ruleId','file_path','path','line','introduced','description')},sort_keys=True))
print('\nORIGINAL_RUNS:')
for r in res.get('runs',[]) or []:
    print('scanner=',r.get('scanner'),'status=',r.get('status'))
    for fld in ('stdout','stderr'):
        s=r.get(fld) or ''
        keep=[]
        for line in s.splitlines():
            if any(q in line.lower() for q in ('javascript-queries/','filesystemrace.ql','missingorigincheck.ql','codeql scanned')):
                keep.append(line)
        if keep:
            print(fld+':')
            for line in keep[:30]: print(line)
PY

printf '\n=== ORIGINAL WORKER HEARTBEAT ===\n'
if [ -f "$HB" ]; then
  printf 'heartbeat_sha256='; sha256sum "$HB" | awk '{print $1}'
  python3 - "$HB" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding='utf-8'))
print(json.dumps(x,indent=2,sort_keys=True)[:12000])
PY
else
  echo 'heartbeat_not_found'
fi

printf '\n=== DB SOURCE OF TRUTH ===\n'
python3 - "$DB" <<'PY'
import sqlite3,sys
con=sqlite3.connect(sys.argv[1]); con.row_factory=sqlite3.Row
pr=con.execute('SELECT id,base_sha,head_sha FROM pull_requests WHERE id=6757').fetchone()
print('pr=',dict(pr))
for r in con.execute("SELECT scanner,rule_id,file_path,line,introduced,created_at FROM scanner_findings WHERE case_id=3581 ORDER BY id"):
    print('finding=',dict(r))
for r in con.execute("SELECT scanner,status,started_at,finished_at,stdout,stderr FROM scanner_runs WHERE case_id=3581 AND scanner LIKE 'codeql%' ORDER BY id"):
    d=dict(r)
    print('run=',{k:d[k] for k in ('scanner','status','started_at','finished_at','stdout')})
PY

printf '\n=== CURRENT SCANNER CODE HASHES ===\n'
printf 'codeql_scanner_py_sha256='; sha256sum "$MINER/src/scanners/codeql_scanner.py" | awk '{print $1}'
printf 'distributed_codeql_pipeline_py_sha256='; sha256sum "$MINER/src/distributed/codeql_pipeline.py" | awk '{print $1}'

printf '\n=== DIAGNOSIS HINTS ===\n'
echo 'If artifact head_sha != DB head_sha: original result was attached to wrong source snapshot.'
echo 'If artifact/worker records a different CodeQL executable/version/path: toolchain mismatch.'
echo 'If both match and original artifact itself contains the two findings: result is historical but not reproducible today; next suspect is extractor/runtime state or a historical scanner/import bug.'
echo 'STATUS=PASS'
