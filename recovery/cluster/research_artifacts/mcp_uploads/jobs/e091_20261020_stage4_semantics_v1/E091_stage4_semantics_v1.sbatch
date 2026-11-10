#!/bin/bash
#SBATCH --job-name=E091_stage4_visual_v1
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import numpy as np,json,hashlib
from collections import defaultdict,Counter
R=Path('/home-mscluster/astrauss/e090_single_game_stage4_causality/E090_vc33_71874')
with np.load(R/'E090_STAGE4_HISTORY_FRAMES.npz') as z:
 def parts(f):
  seen=np.zeros((64,64),bool);by=defaultdict(list)
  for y in range(64):
   for x in range(64):
    if seen[y,x]:continue
    color=int(f[y,x]); stack=[(y,x)];seen[y,x]=True;cells=[]
    while stack:
     yy,xx=stack.pop();cells.append((yy,xx))
     for ny,nx in ((yy-1,xx),(yy+1,xx),(yy,xx+1),(yy,xx-1)):
      if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and int(f[ny,nx])==color:
       stack.append((ny,nx));seen[ny,nx]=True
    if 1<=len(cells)<=150:
     ys=np.array([c[0] for c in cells]);xs=np.array([c[1] for c in cells])
     by[color].append([len(cells),int(xs.min()),int(xs.max()),int(ys.min()),int(ys.max()),
      round(float(xs.mean()),1),round(float(ys.mean()),1)])
  return {k:sorted(v,key=lambda q:(-q[0],q[1],q[3])) for k,v in by.items()}
 base=z['neutral']
 print('E091_STAGE4_OBSERVED_OBJECT_COMPONENTS',json.dumps(parts(base[0])),flush=True)
 for k in sorted(z.files):
  if k=='neutral':continue
  frames=z[k];a=base[0];b=frames[0];end=frames[-1]
  difference=(a!=b); yy,xx=np.where(difference)
  boxes=[int(xx.min()),int(yy.min()),int(xx.max()),int(yy.max())] if len(xx) else None
  print('E091_STAGE4_ACTION_DELTA',json.dumps({'action':k,
   'first_step_pixel_diffs':int(difference.sum()),'first_difference_box':boxes,
   'last_step_pixel_diffs':int((base[-1]!=end).sum()),
   'color_changes':[[[int(v),int(w)],int(n)] for (v,w),n in Counter((int(v),int(w)) for v,w in zip(a[difference],b[difference])).most_common()],
   'first_changed_components':parts(b).get(4,[]) + parts(b).get(11,[])}),flush=True)
PY