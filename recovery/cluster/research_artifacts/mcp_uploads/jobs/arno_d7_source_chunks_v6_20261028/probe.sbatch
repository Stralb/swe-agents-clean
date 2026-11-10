#!/bin/bash
#SBATCH --job-name=d7probe
#SBATCH --partition=stampede
#SBATCH --time=00:01:00
python3 - <<'PY'
print('ok')
PY
