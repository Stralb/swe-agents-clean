#!/bin/bash
#SBATCH --job-name=E083_stage3_objects
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import defaultdict
import numpy as np,json
p=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
with np.load(p/'repeat_frames.npz') as d:img=d['frames'][91]
by=defaultdict(list);seen=np.zeros((64,64),dtype=bool)
for y in range(64):
 for x in range(64):
  if seen[y,x]:continue
  col=int(img[y,x]);todo=[(y,x)];seen[y,x]=True;cells=[]
  while todo:
   yy,xx=todo.pop();cells.append((yy,xx))
   for ny,nx in ((yy+1,xx),(yy-1,xx),(yy,xx+1),(yy,xx-1)):
    if 0<=ny<64 and 0<=nx<64 and not seen[ny,nx] and int(img[ny,nx])==col:
     todo.append((ny,nx));seen[ny,nx]=True
  if 1<=len(cells)<=128:
   cx=round(sum(xx for yy,xx in cells)/len(cells));cy=round(sum(yy for yy,xx in cells)/len(cells))
   by[col].append((len(cells),cx,cy,min(xx for yy,xx in cells),max(xx for yy,xx in cells),min(yy for yy,xx in cells),max(yy for yy,xx in cells)))
for col in sorted(by):
 print('COLOR_OBJECTS',col,'n',len(by[col]),'top_small',sorted(by[col])[:16],'largest',sorted(by[col],reverse=True)[:6],flush=True)
print('STAGE3_COLOR_COUNTS',dict(zip(*np.unique(img,return_counts=True))),flush=True)
PY