#!/bin/bash
#SBATCH --job-name=rlpaper-records
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=5G
#SBATCH --time=00:12:00
set -euo pipefail
python3 - <<'PY'
from pathlib import Path
from collections import defaultdict
import json,statistics,collections
root=Path('/home-mscluster/astrauss/RL-ARC-AGI-3-Project/results')
groups=defaultdict(list); bad=[]
for p in root.rglob('record.json'):
 try:
  r=json.loads(p.read_text())
  c=r.get('identity',{}).get('config',{})
  algo=c.get('algo');version=c.get('version')
  if not algo:continue
  stage=p.relative_to(root).parts[0]
  groups[(stage,algo,version)].append((c.get('game'),c.get('seed'),r.get('official_score',{}),r.get('learner',{}),r.get('counters',{}),r.get('status'),r.get('error')))
 except Exception as e:bad.append(str(p)+':'+str(e))
print('TOTAL_VALID_RECORDS',sum(map(len,groups.values())),'GROUPS',len(groups),'BAD',len(bad))
print('GROUP STAGE ALGO VER N N_OK N_GAMES N_SEEDS TOTAL_LVLS MEAN_SCORE SUM_ACTIONS N_UPDATED N_UPDATES_DISABLED')
for (st,alg,v),z in sorted(groups.items()):
 ok=[x for x in z if x[5]!='error' and x[2]]
 lv=sum((x[2].get('levels_completed') or 0) for x in ok)
 sc=[x[2].get('score') for x in ok if isinstance(x[2].get('score'),(int,float))]
 ac=sum((x[4].get('scorer_actions') or 0) for x in ok)
 trained=sum((x[3].get('gradient_steps') or 0)>0 for x in ok)
 disabled=sum(x[3].get('updates_disabled') is True for x in ok)
 print(st,alg,v,len(z),len(ok),len({x[0] for x in ok}),len({x[1] for x in ok}),lv,round(statistics.mean(sc),6) if sc else None,ac,trained,disabled)
print('PPO ALL:')
for k,z in sorted(groups.items()):
 if k[1]=='ppo':
  print(k,'count',len(z),'games',list(dict.fromkeys(x[0] for x in z))[:35],'seeds',list(dict.fromkeys(x[1] for x in z))[:30],'sample learner',z[0][3],'statuses',collections.Counter(x[5] for x in z))
print('BAD SAMPLE',bad[:8])
PY
