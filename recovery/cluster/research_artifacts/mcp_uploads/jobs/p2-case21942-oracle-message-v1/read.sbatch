#!/bin/bash
#SBATCH --job-name=p2oracle-text
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json,os
root=Path.home()/'research_artifacts/prevention_pilot_phase2/two_new_clean_baselines_eval_job70031/21942'
out=Path.home()/'research_artifacts/prevention_pilot_phase2'/('case21942_oracle_message_job'+os.environ['SLURM_JOB_ID'])
out.mkdir(exist_ok=True)
result={}
for name in ['base','generated','historical']:
 doc=json.loads((root/(name+'.sarif')).read_text())
 findings=[]
 for run in doc['runs']:
  for r in run.get('results',[]):
   if r.get('ruleId')=='js/insecure-temporary-file':
    p=r.get('locations',[{}])[0].get('physicalLocation',{})
    m=r.get('message',{})
    findings.append({'file':p.get('artifactLocation',{}).get('uri'),'line':p.get('region',{}).get('startLine'),
      'message_text':m.get('text'),'formatted':r.get('properties',{}).get('formattedMessage',{}).get('text'),
      'message_markdown':m.get('markdown'),'ruleId':r.get('ruleId')})
 result[name]={'count':len(findings),'findings':findings}
(out/'CODEQL_MESSAGES.json').write_text(json.dumps(result,indent=2)+'\n')
for name in ['generated','historical']:
 print(name)
 for f in result[name]['findings']:
  if f['file']=='__tests__/codex-plugin.test.ts':
   print(json.dumps(f,ensure_ascii=False),flush=True)
PY
