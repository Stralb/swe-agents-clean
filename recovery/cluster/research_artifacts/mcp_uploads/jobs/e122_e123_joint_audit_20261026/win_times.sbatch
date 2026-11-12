#!/bin/bash
#SBATCH --job-name=e123wintime
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
python3 - <<'PY'
from pathlib import Path
import json,csv
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
out=root/'e122_e123_joint_audit_20261026/analysis'
experiments=[('E123_L1',root/'teammate_prior_e123_20261026/level1',('l1_d14_salience','l1_random_prior','l1_trained_prior')),
('E123_L2',root/'teammate_prior_e123_20261026/results',('peer_salience','peer_trained','peer_gated')),
('E122',root/'click_feedback_e122_20261026/results',('feedback_rescue_l2','local_credit_l2','rescue_credit_l2'))]
rows=[]
for family,folder,arms in experiments:
 base=folder/'seed76/baseline'
 for arm in arms:
  btot=ctot=0;earlier=later=same=0;missing=0
  cases=[]
  for f in sorted(base.glob('*.json')):
   if f.name=='summary.json':continue
   x=json.loads(f.read_text())['summary']
   y=json.loads((folder/'seed76'/arm/f.name).read_text())['summary']
   xb={int(w['level']):int(w['step']) for w in x['wins']}
   yb={int(w['level']):int(w['step']) for w in y['wins']}
   for lvl,bstep in xb.items():
    if lvl not in yb:
     missing+=1
     continue
    cstep=yb[lvl]
    diff=cstep-bstep
    btot+=bstep;ctot+=cstep
    earlier+=int(diff<0);later+=int(diff>0);same+=int(diff==0)
    if diff!=0:cases.append(f.name[:4]+' L'+str(lvl)+':'+str(diff))
    rows.append({'study':family,'arm':arm,'game':f.name[:4],'level':lvl,
      'baseline_win_step':bstep,'variant_win_step':cstep,'action_step_difference':diff})
  print('WIN_TIME',family,arm,'MATCHED',earlier+later+same,'EARLIER',earlier,'LATER',later,'SAME',same,
       'LOSSES',missing,'MATCHED_BASE_TOTAL',btot,'VARIANT_TOTAL',ctot,'DIFF',ctot-btot,'CASES',','.join(cases),flush=True)
with (out/'paired_win_times.csv').open('w',newline='') as file:
 writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('WIN_TIME_CSV',out/'paired_win_times.csv')
PY
