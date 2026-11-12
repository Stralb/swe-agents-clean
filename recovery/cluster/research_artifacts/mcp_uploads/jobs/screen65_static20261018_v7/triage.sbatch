#!/bin/bash
#SBATCH --job-name=screen65_triage
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
python3 - <<'PY'
from pathlib import Path
import json,os,collections
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
basedir=root/'screen65_codeql_job70675'
out=root/('screen65_triage_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=False)
cases=[3581,8152,3429]
allout=[]
for cid in cases:
 f=basedir/('CASE_%05d'%cid)
 old=json.loads((f/'RESULT.json').read_text())
 added={(v['rule'],v['path'],v['line']) for v in old.get('findings',{}).get('new_strong_findings',[])}
 sarif=json.loads((f/'after.sarif').read_text())
 for run in sarif.get('runs',[]):
  for item in run.get('results',[]):
   p=(item.get('locations') or [{}])[0].get('physicalLocation',{})
   uri=p.get('artifactLocation',{}).get('uri')
   ln=p.get('region',{}).get('startLine')
   key=(item.get('ruleId'),uri,ln)
   if key not in added:continue
   steps=[]
   for flow in item.get('codeFlows',[]):
    for thread in flow.get('threadFlows',[]):
     for row in thread.get('locations',[]):
      loc=row.get('location',{})
      phy=loc.get('physicalLocation',{})
      steps.append({'file':phy.get('artifactLocation',{}).get('uri'),
        'line':phy.get('region',{}).get('startLine'),'text':loc.get('message',{}).get('text','')[:120]})
   allout.append({'case':cid,'rule':item.get('ruleId'),'source_type':old.get('source_type'),
    'file':uri,'line':ln,'message':item.get('message',{}).get('text'),'flow_steps':steps[:65],
    'flow_total':len(steps)})
(out/'CANDIDATE_CODEQL_TRACE_REVIEW.json').write_text(json.dumps(allout,indent=2,ensure_ascii=False)+'\n')
print('WARNINGS_TRIAGED',len(allout),flush=True)
for x in allout:print(x['case'],x['rule'],x['file'],x['line'],'steps',x['flow_total'],flush=True)
PY