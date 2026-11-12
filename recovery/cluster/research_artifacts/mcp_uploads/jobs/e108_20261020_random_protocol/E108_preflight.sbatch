#!/bin/bash
#SBATCH --job-name=E108_random_preflight
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python - <<'PY'
from pathlib import Path
import json,hashlib
H=Path('/home-mscluster/astrauss')
paths=[H/'RL-ARC-AGI-3-Project/src/adapter.py',H/'E074_HUMAN_TO_POLICY_20261019/vendor/e068/code/e068_split.py',H/'RL-ARC-AGI-3-Project/src/e027/reproducibility.py']
for p in paths:
 print('SOURCE',str(p),'EXISTS',p.is_file(),flush=True)
 if p.is_file():
  t=p.read_text();print('SHA256',hashlib.sha256(p.read_bytes()).hexdigest(),flush=True)
  print(t[:26000],flush=True)
print('E108_PREFLIGHT_FINISHED',flush=True)
PY