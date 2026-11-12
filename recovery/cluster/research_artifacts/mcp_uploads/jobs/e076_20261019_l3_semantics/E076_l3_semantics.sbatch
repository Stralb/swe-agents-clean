#!/bin/bash
#SBATCH --job-name=E076_l3_semantics
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
from collections import Counter
import json,numpy as np
p=Path('/home-mscluster/astrauss/e075_one_game_runs/E075_VC33_71743')
with np.load(p/'repeat_frames.npz') as z:frames=z['frames']
events=[json.loads(x) for x in (p/'repeat.jsonl').read_text().splitlines()]
for i in range(91,min(len(events),127)):
 x,y=frames[i],frames[i+1];mask=x!=y
 changes=Counter((int(a),int(b)) for a,b in zip(x[mask],y[mask]))
 event=events[i]
 print('STEP',i,'xy',event['xy'],'reason',event['reason'],'pixels',int(mask.sum()),'top',changes.most_common(5),'delta7',int((y==7).sum()-(x==7).sum()),'delta4',int((y==4).sum()-(x==4).sum()),flush=True)
PY