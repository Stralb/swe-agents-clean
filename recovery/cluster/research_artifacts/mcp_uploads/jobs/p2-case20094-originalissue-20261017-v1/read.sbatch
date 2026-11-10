#!/bin/bash
#SBATCH --job-name=p2case20094audit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json,os
p=Path.home()/'research_artifacts/prevention_pilot_phase2/case_screen_issue_recovery_v1_job69671/RESEARCHER_CORPUS_ISSUES_24.json'
data=json.loads(p.read_text())
print('ROOT_TYPE',type(data).__name__, 'ROOT_KEYS',list(data.keys())[:18] if isinstance(data,dict) else 'list',flush=True)
matches=[]
def crawl(node,depth=0):
 if isinstance(node,dict):
  if 'lidge-jun/opencodex' in str(node.get('repository','')) or node.get('case_id')==20094 or node.get('case_id')=='20094':
   matches.append(node)
  else:
   for k,v in node.items():
    if depth<9:crawl(v,depth+1)
 elif isinstance(node,list):
  for v in node:
   if depth<9:crawl(v,depth+1)
crawl(data)
out=Path.home()/'research_artifacts/prevention_pilot_phase2'/('case20094_preissue_inspection_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True)
print('MATCHES',len(matches),flush=True)
for i,m in enumerate(matches[:4]):
 (out/('MATCH_'+str(i)+'.json')).write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
 print('MATCH',i,'FIELDS',list(m.keys())[:40],flush=True)
 print('TEXT',json.dumps(m,ensure_ascii=False)[:8000],flush=True)
PY
