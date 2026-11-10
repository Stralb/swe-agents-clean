#!/bin/bash
#SBATCH --job-name=rl-paper-smoke2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:12:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONPATH=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026/runtime/python_site
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - <<'PY'
import arc_agi,torch,time
from src.config import RunConfig
from src.run import run
print('TORCH',torch.__version__,'ARC',arc_agi.__file__,flush=True)
c=RunConfig(algo='ppo',version='V0',game='ft09',seed=201,env_seed=47,budget=100,threads=1,tag='completion-smoke2')
t=time.time()
r=run(c,save_checkpoint=False)
print('PPO_SMOKE',r['status'],r['error'],r['counters'],r['official_score'],r['learner'],r['cost'], 'wall',time.time()-t,flush=True)
PY
