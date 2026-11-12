#!/bin/bash
#SBATCH --job-name=e123legalobs
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python - <<'PY'
import sys,hashlib,json,collections,numpy as np
from pathlib import Path
b=Path('/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026')
from arc_agi import Arcade,OperationMode
from arcengine import GameAction,GameState
envroot=b/'runtime/environment_files'
gameids=sorted(x.name for x in envroot.iterdir() if x.is_dir())
a=Arcade(operation_mode=OperationMode.OFFLINE,environments_dir=str(envroot),recordings_dir=str(b/'runtime/recordings'))
rows=[]
for gameid in gameids:
 env=a.make(gameid,seed=47,save_recording=False)
 obs=env.observation_space
 if obs.state==GameState.NOT_PLAYED:obs=env.step(GameAction.RESET)
 legal=tuple(sorted(int(getattr(x,'value',x)) for x in obs.available_actions))
 f=np.asarray(obs.frame[-1],np.uint8)
 colors,counts=np.unique(f,return_counts=True)
 info={'game':gameid,'legal_actions':legal,'n_colors':len(colors),'largest_color_fraction':round(float(counts.max()/4096.),3),'pixel_entropy':round(float(-sum(v*np.log2(v) for v in counts/4096.)),3)}
 rows.append(info)
 print('INITIAL',json.dumps(info),flush=True)
print('ALL_INITIAL_OBSERVATIONS_COLLECTED',len(rows),flush=True)
PY
