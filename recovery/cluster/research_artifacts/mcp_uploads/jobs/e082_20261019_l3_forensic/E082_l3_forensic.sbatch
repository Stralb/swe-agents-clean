#!/bin/bash
#SBATCH --job-name=E082_l3_replay_forensic
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:06:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import numpy as np,json,hashlib
root=Path('/home-mscluster/astrauss/e075_one_game_runs')
for seed,dirname in ((28901,'E075_VC33_71743'),(28902,'E075_VC33_71744_seed28902'),(28903,'E075_VC33_71744_seed28903')):
 p=root/dirname; rep=json.loads((p/'E075_REPORT.json').read_text())
 r=next(x for x in rep['rows'] if x['mode']=='repeat')
 with np.load(p/'repeat_frames.npz') as d:frames=d['frames']
 events=[json.loads(l) for l in (p/'repeat.jsonl').read_text().splitlines()]
 assert hashlib.sha256((p/'repeat.jsonl').read_bytes()).hexdigest()==r['trace_sha256']
 start=next(i for i,e in enumerate(events) if e['native_level_reward']>0 and e['progress']>=2)
 print('L3_START',seed,'native_frame_idx',start+1,'native_action',events[start]['action_number'],
       'events',len(events),'levels',r['levels_completed'],flush=True)
 for i in list(range(start+1,min(start+18,len(events))))+list(range(max(start+18,len(events)-12),len(events))):
  ev=events[i]; a=frames[i];b=frames[i+1];mask=a!=b
  before_counts=Counter(map(int,a.ravel()));after_counts=Counter(map(int,b.ravel()))
  diff=list(sorted(((col,after_counts[col]-before_counts[col]) for col in set(before_counts)|set(after_counts) if after_counts[col]!=before_counts[col]),key=lambda x:abs(x[1]),reverse=True))
  non_timer=int((mask&~((a==7)&(b==4))).sum())
  print('FRAME_EVENT',json.dumps({'seed':seed,'i':i,'step':ev['action_number'],'action':ev['action_id'],
    'xy':ev['xy'],'reason':ev['reason'],'progress':ev['progress'],'reward':ev['native_level_reward'],
    'changed':int(mask.sum()),'non_timer_changed':non_timer,'top_color_deltas':diff[:5],
    'state':ev.get('game_state')}),flush=True)
PY