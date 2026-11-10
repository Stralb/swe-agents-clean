#!/bin/bash
#SBATCH --job-name=trace15686
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
python3 - <<'PY'
from pathlib import Path
import json,os
root=Path.home()/'research_artifacts/prevention_pilot_phase2'
paths=[
 ('O','screen5_eval_15686_job70129/patched.sarif'),
 ('G_or_W_1','GW_screeneval_case15686_file1_job70178/patched.sarif'),
 ('G_or_W_2','GW_screeneval_case15686_file2_job70175/patched.sarif'),
 ('hist','screen5_hist_15686_job70155/head.sarif')
]
out=root/('trace15686_job'+os.environ['SLURM_JOB_ID']);out.mkdir(exist_ok=False)
entries=[]
for name,rel in paths:
 data=json.loads((root/rel).read_text())
 for run in data.get('runs',[]):
  for r in run.get('results',[]):
   if r.get('ruleId')!='js/file-access-to-http':continue
   steps=[]
   for flow in r.get('codeFlows',[]):
    for tf in flow.get('threadFlows',[]):
     for s in tf.get('locations',[]):
      loc=s.get('location',{})
      phy=loc.get('physicalLocation',{})
      steps.append({'file':phy.get('artifactLocation',{}).get('uri'),'line':phy.get('region',{}).get('startLine'),'msg':loc.get('message',{}).get('text')})
   phy=r.get('locations',[{}])[0].get('physicalLocation',{})
   entries.append({'variant':name,'sinkfile':phy.get('artifactLocation',{}).get('uri'),'sinkline':phy.get('region',{}).get('startLine'),'msg':r.get('message',{}).get('text'),'steps':steps})
(out/'TRACES.json').write_text(json.dumps(entries,indent=2,ensure_ascii=False)+'\n')
for x in entries:
 print(x['variant'],x['sinkfile'],x['sinkline'], 'steps',len(x['steps']))
 print('  '.join(str(s['file'])+':'+str(s['line'])+' '+str(s['msg']) for s in x['steps'][:18]))
PY