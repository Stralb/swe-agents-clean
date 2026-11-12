#!/bin/bash
#SBATCH --job-name=E085_state_factorization
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
import numpy as np, json, collections
from pathlib import Path
dir=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855')
with np.load(dir/'E084_CONTROLS_FRAMES.npz') as d:
 base=d['action_1318'][0]
 counts=np.array([(base[2:55,x:x+1]==5).sum() for x in range(64)])
 active=[int(x) for x in np.where(counts>9)[0] if 3<x<61]
 groups=[]
 for x in active:
  if not groups or x>groups[-1][-1]+1:groups.append([x])
  else:groups[-1].append(x)
 print('VERTICAL_GRAY_COMPONENTS',groups,flush=True)
 ends=[5]+[int(round(np.mean(v))) for v in groups]+[58]
 print('SEGMENT_BOUNDS',ends,flush=True)
 def segment(f):
  black=[];tops=[];yellow=[];green=[]
  for x0,x1 in zip(ends[:-1],ends[1:]):
   xl=max(0,x0+2);xr=min(64,x1-1)
   sl=f[3:58,xl:xr]
   black.append(int((sl==0).sum()))
   green.append(int((sl==3).sum()))
   heights=[]
   for x in range(xl,xr):
    ys=np.argwhere(f[3:58,x]==0)
    heights.append(int(ys.min()+3) if len(ys) else 58)
   tops.append(int(round(float(np.median(heights)))))
   yellow.append(int((sl==4).sum()))
  return {'black':black,'black_top_rows':tops,'yellow_count':yellow,'green':green}
 baseline=segment(base)
 print('BASELINE_SEGMENTS',json.dumps(baseline),flush=True)
 for x in (12,16,24,28,34,38,46,50):
  idx=6+56*64+x
  f=d['action_'+str(idx)][0]
  h=segment(f)
  print('OPERATOR_SEGMENT_DELTA',json.dumps({'control_x':x,'segment_black_delta':[a-b for a,b in zip(h['black'],baseline['black'])],
   'black_top_delta':[a-b for a,b in zip(h['black_top_rows'],baseline['black_top_rows'])],
   'total_black_delta':sum(h['black'])-sum(baseline['black']),
   'yellow_delta':[a-b for a,b in zip(h['yellow_count'],baseline['yellow_count'])],
   'total_changed':int((f!=base).sum())},sort_keys=True),flush=True)
PY