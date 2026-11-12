#!/bin/bash
#SBATCH --job-name=e125scoreaudit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
python3 - <<'PY'
import csv,json,hashlib
from pathlib import Path
R=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs')
base=R/'sparse_click_transfer_e125_20261026'
meta={p.name:json.loads(next(p.glob('*/metadata.json')).read_text()) for p in (R/'click_diversity_e121_20261026/runtime/environment_files').iterdir() if p.is_dir()}
assert len(meta)==25
src=(R/'n117_kaggle_20261026_dataset1/private_dataset/my_agent.py').read_bytes()
assert hashlib.sha256(src).hexdigest()=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
def score(ob,g):
 human=meta[g]['baseline_actions']
 denom=len(human)*(len(human)+1)/2.
 numer=0.;last=0
 for win in ob['summary']['wins']:
  j=int(win['level']);spent=int(win['step'])-last;last=int(win['step'])
  numer+=j*min(115.,100.*(human[j-1]/spent)**2)
 levels=int(ob['summary']['levels_completed'])
 return min(numer/denom,sum(range(1,levels+1))/denom*100.)
rows=[]
for seed in (76,77,78):
 arms=['baseline','sparse80_trained','sparse80_random','sparse80_salience']+(['sparse70_trained'] if seed==76 else [])
 records={}
 for arm in arms:
  d={}
  for game in sorted(meta):
   obj=json.loads((base/'results'/('seed'+str(seed))/arm/(game+'.json')).read_text())
   assert 'fatal' not in obj,(seed,arm,game)
   s=obj['summary'];t=obj['trajectory']
   assert s['source_sha256']=='0663845070e47a053076db54243c3445921a06b4bf0908b7b233c263da423bfa'
   assert s['policy_seed']==seed and s['native_seed']==47
   assert len(t)==s['charged_sdk_actions'] and sum(r['reward'] for r in t)==s['levels_completed']
   assert all(t[i]['post']==t[i+1]['pre'] for i in range(len(t)-1))
   d[game]=obj
  records[arm]=d
  mean=sum(score(x,g) for g,x in d.items())/25
  completed=sum(x['summary']['levels_completed'] for x in d.values())
  row={'seed':seed,'arm':arm,'completed_levels':completed,
       'L1':sum(x['summary']['l1'] for x in d.values()),'L2':sum(x['summary']['l2'] for x in d.values()),
       'mean_native_sdk_score':round(mean,10)}
  rows.append(row)
  print('E125_SCORE',json.dumps(row),flush=True)
 for arm in arms[1:]:
  b=records['baseline'];v=records[arm]
  plus=[];minus=[];score_d=[]
  for g in sorted(meta):
   assert b[g]['summary']['initial_frame_sha']==v[g]['summary']['initial_frame_sha']
   dif=v[g]['summary']['levels_completed']-b[g]['summary']['levels_completed']
   if dif>0:plus.append(g)
   if dif<0:minus.append(g)
   dd=score(v[g],g)-score(b[g],g)
   if abs(dd)>1e-9:score_d.append((g,round(dd,6)))
  print('E125_PAIRED',seed,arm,'LEVEL_GAIN',plus,'LEVEL_LOSS',minus,'SDK_SCORE_DIFF',score_d,flush=True)
with (base/'scores_3seeds.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('E125_SCORE_AUDIT_COMPLETE')
PY
