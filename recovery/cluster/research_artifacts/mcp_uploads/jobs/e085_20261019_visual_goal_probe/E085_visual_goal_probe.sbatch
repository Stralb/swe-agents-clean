#!/bin/bash
#SBATCH --job-name=E085_visual_height_law
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
import numpy as np,json
from pathlib import Path
P=Path('/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_71855/E084_CONTROLS_FRAMES.npz')
Xs=[9,20,31,42,53]
with np.load(P) as d:
 for label,key in [('neutral','action_1318'),('move1_left','action_3602'),('move2_left','action_3614'),('move3_left','action_3624'),('move4_left','action_3636'),('move4_right','action_3640')]:
  f=d[key][0]
  out=[]
  for x in Xs:
   series=[int(f[y,x]) for y in range(3,59)]
   segments=[];first=3
   for i in range(1,len(series)+1):
    if i==len(series) or series[i]!=series[i-1]:
     if first<59 and (series[i-1]!=3):segments.append((series[i-1],first,2+i))
     first=3+i
   black=np.where(f[3:58,x]==0)[0]
   out.append({'x':x,'color_runs':segments,'black_from':int(black.min()+3) if len(black) else None,
    'black_height':int(len(black))})
  print('HEIGHT_MEASUREMENT',json.dumps({'action':label,'columns':out}),flush=True)
PY