#!/bin/bash
#SBATCH --job-name=e124scoreaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
python3 - <<'PY'
import csv,json
from pathlib import Path
root=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
folder=root/'click_breakthrough_e124_20261026/results/seed76'
envs=root/'click_diversity_e121_20261026/runtime/environment_files'
metadata={p.name:json.loads(next(p.glob('*/metadata.json')).read_text()) for p in envs.iterdir() if p.is_dir()}
arms=('baseline','prune_bg','prune_broad','contingency','selection_chain')
def sdk_score(obj,g):
 s=obj['summary'];meta=metadata[g];human=list(meta['baseline_actions']);total=len(human)
 cost=0;last=0
 for row in s['wins']:
  level=int(row['level']);steps=int(row['step'])-last;last=int(row['step'])
  cost+=level*min(115.,100.*(human[level-1]/steps)**2)
 return min(cost/(total*(total+1)/2.),sum(range(1,s['levels_completed']+1))/(total*(total+1)/2.)*100.)
games=sorted(metadata)
rows=[];detail=[]
for arm in arms:
 d={}
 for game in games:
  ob=json.loads((folder/arm/(game+'.json')).read_text())
  assert 'fatal' not in ob
  d[game]=(ob,sdk_score(ob,game))
 mean=sum(q[1] for q in d.values())/25
 wins=sum(q[0]['summary']['levels_completed'] for q in d.values())
 baseline={}
 if arm!='baseline':
  for game in games:
   b=json.loads((folder/'baseline'/(game+'.json')).read_text())
   bs=sdk_score(b,game)
   delta=d[game][1]-bs
   if abs(delta)>1e-8:
    detail.append({'arm':arm,'game':game,'delta_score':round(delta,8),
        'baseline':round(bs,8),'candidate':round(d[game][1],8),
        'baseline_levels':b['summary']['levels_completed'],
        'candidate_levels':d[game][0]['summary']['levels_completed'],
        'baseline_win_steps':str(b['summary']['wins']),'candidate_win_steps':str(d[game][0]['summary']['wins'])})
 record={'arm':arm,'games':25,'total_levels':wins,'L1':sum(o['summary']['l1'] for o,_ in d.values()),
         'L2':sum(o['summary']['l2'] for o,_ in d.values()),
         'mean_sdk_score_0_100':round(mean,10)}
 rows.append(record)
 print('E124_SCORED',json.dumps(record,sort_keys=True),flush=True)
print('SCORE_DIFFERENCES',json.dumps(detail),flush=True)
out=root/'click_breakthrough_e124_20261026'
for filename,data in [('scores.csv',rows),('score_changes.csv',detail)]:
 with (out/filename).open('w',newline='') as f:
  if not data:continue
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
print('E124_SCORE_AUDIT_OK')
PY
