#!/bin/bash
#SBATCH --job-name=rl-paper-smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - <<'PY'
from src.config import RunConfig
from src.run import run
import torch,time
print('TORCH',torch.__version__,flush=True)
c=RunConfig(algo='ppo',version='V0',game='ft09',seed=201,env_seed=47,budget=100,threads=1,tag='completion-smoke')
t=time.time()
r=run(c,save_checkpoint=False)
print('PPO_SMOKE',r['status'],r['error'],r['counters'],r['official_score'],r['learner'],r['cost'], 'wall',time.time()-t,flush=True)
PY
