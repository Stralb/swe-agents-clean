#!/bin/bash
#SBATCH --job-name=E076_local_effects
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
import numpy as np,json
from pathlib import Path
p=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
with np.load(p/'repeat_frames.npz') as d:frames=d['frames']
events=[json.loads(x) for x in (p/'repeat.jsonl').read_text().splitlines()]
for i in (90,107,108,110,111,117,125,126,135,146):
 a,b=frames[i],frames[i+1];mask=a!=b;xy=np.argwhere(mask)
 meaningful=mask&~((a==7)&(b==4))
 xy2=np.argwhere(meaningful)
 def box(z):return [int(z[:,1].min()),int(z[:,0].min()),int(z[:,1].max()),int(z[:,0].max())] if len(z) else None
 print('EFFECT',i,'user_click',events[i]['xy'],'frame_count',int(mask.sum()),
 'non_timer_count',int(meaningful.sum()),'non_timer_box',box(xy2),
 'score',events[i]['native_level_reward'],flush=True)
 for col in (0,3,4,5,7,9,11,14,15):
  z=np.argwhere(a==col);zz=np.argwhere(b==col)
  pre=int(len(z));post=int(len(zz))
  if pre!=post:print(' CLR',col,pre,post,'delta',post-pre,flush=True)
PY