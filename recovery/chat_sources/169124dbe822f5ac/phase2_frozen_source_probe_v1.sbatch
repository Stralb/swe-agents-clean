#!/usr/bin/env bash
#SBATCH --job-name=p2_source_probe
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:08:00
#SBATCH --output=p2_source_probe_%j.out
#SBATCH --error=p2_source_probe_%j.err
set -euo pipefail
ROOT="$HOME/research_artifacts/prevention_pilot_phase2"
REPO="$HOME/new/malicious-issue-miner-rate-smart"
cd "$ROOT"
if [ -f "$REPO/.env.cluster" ]; then set -a; source "$REPO/.env.cluster"; set +a; fi
source "$REPO/.venv/bin/activate"
mkdir -p case_screen_source_probe_v1
python - <<'PY'
import csv, json, os, re, sqlite3, hashlib
from pathlib import Path
from urllib.parse import quote
root=Path.home()/"research_artifacts/prevention_pilot_phase2"
output=root/'case_screen_source_probe_v1'
output.mkdir(exist_ok=True)
sources=[Path.home()/'new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.db',Path.home()/'new/malicious-issue-miner-rate-smart/data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db']
targets=['3882','313','10339','3582','7680','17062','21682']
info={'targets':targets,'databases':[],'warning':'SCHEMA PROBE ONLY. Returned issue content, if any, must be verified as historically pre-PR; corpus capture alone is not proof of contemporaneous issue text.'}
for i,db in enumerate(sources):
 rec={'database':str(db),'exists':db.is_file(),'table_summaries':[],'candidate_issue_rows':[]}
 info['databases'].append(rec)
 if not db.is_file(): continue
 rec['bytes']=db.stat().st_size
 try:
  con=sqlite3.connect('file:'+quote(str(db))+'?mode=ro',uri=True,timeout=12)
  con.execute('PRAGMA query_only=ON')
  schema=con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
  for (name,) in schema:
   safe_name='"'+name.replace('"','""')+'"'
   cols=[row[1] for row in con.execute(f'PRAGMA table_info({safe_name})')]
   low=[c.lower() for c in cols]
   interesting=[c for c in cols if any(k in c.lower() for k in ('issue','case','repo','commit','sha','snapshot','workflow','pr_','pull_','body','task','prompt'))]
   if not interesting and not any(k in name.lower() for k in ('case','issue','workflow','pull')): continue
   rec['table_summaries'].append({'table':name,'columns':cols[:100]})
   # The smaller primary DB is queried. Large snapshot is schema-only to avoid expensive scans.
   if i>0: continue
   keys=[c for c in cols if c.lower() in ('case_id','workflow_id','case_number','source_case_id')]
   if not keys and name.lower() in ('cases','workflows','issue_pr_cases'): keys=[c for c in cols if c.lower()=='id']
   if not keys: continue
   readable=[c for c in cols if any(s in c.lower() for s in ('issue','case','repo','title','body','created','updated','sha','url'))][:20]
   for key in keys[:2]:
    projection=list(dict.fromkeys([key]+readable)); qcols=', '.join('"'+c.replace('"','""')+'"' for c in projection)
    qkey='"'+key.replace('"','""')+'"'
    try:
     qry=f'SELECT {qcols} FROM {safe_name} WHERE CAST({qkey} AS TEXT) IN ({",".join("?" for _ in targets)}) LIMIT 25'
     c=con.execute(qry,targets)
     for tup in c.fetchall():
      obj={}
      for k,v in zip(projection,tup):
       if isinstance(v,bytes): obj[k]={'binary_bytes':len(v),'sha256':hashlib.sha256(v).hexdigest()}
       elif isinstance(v,str): obj[k]=v[:18000]
       else: obj[k]=v
      rec['candidate_issue_rows'].append({'table':name,'lookup_key':key,'row':obj})
    except sqlite3.Error as ex:
     rec.setdefault('query_errors',[]).append({'table':name,'key':key,'error':str(ex)[:300]})
  con.close()
 except Exception as e:rec['error']=repr(e)
path=output/'PINNED_SOURCE_PROBE.json';path.write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
print('SOURCE_PROBE_COMPLETE',str(path),'dbs',len(info['databases']))
for x in info['databases']:
 print('DB',x['database'],'exists',x['exists'],'candidate_tables',len(x['table_summaries']),'matching_rows',len(x['candidate_issue_rows']),'error',x.get('error','none'))
PY
