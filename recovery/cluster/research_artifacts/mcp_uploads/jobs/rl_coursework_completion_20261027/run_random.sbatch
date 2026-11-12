#!/bin/bash
#SBATCH --job-name=rl-random-ref
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:18:00
#SBATCH --array=0-11%4
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/rl_coursework_completion_20261027
export PYTHONPATH=/home-mscluster/astrauss/RL-ARC-AGI-3-Project:/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026/runtime/python_site
cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" - "$SLURM_ARRAY_TASK_ID" "$ROOT/records" <<'PY'
import json,sys
from pathlib import Path
from src.config import RunConfig
from src.run import run
q=int(sys.argv[1]);p=Path(sys.argv[2]);p.mkdir(exist_ok=True,parents=True)
game=('ar25','g50t','s5i5','vc33')[q%4];seed=(301,302,303)[q//4]
out=p/f'random_V0_{game}_{seed}.json'
if out.exists():print('ALREADY_PRESENT');sys.exit(0)
c=RunConfig(algo='random_type',version='V0',game=game,seed=seed,env_seed=47,budget=256,threads=1,tag='matched_public_20261027')
r=run(c);r.pop('_learner',None);r.pop('scorecard',None)
r['study']={'algorithm':'random','arm':'V0','game':game,'policy_seed':seed,'native_seed':47,
            'public_exposure':'previously studied public','max_scorer_actions':256}
out.write_text(json.dumps(r,indent=2,default=float))
print(out.name, r['error'],r['official_score'],r['counters'],flush=True)
PY
