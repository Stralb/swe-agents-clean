#!/bin/bash
#SBATCH --job-name=E108_random5_round5
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' 5db4392d135eb08e736609f77c92b5fa431af0ba419b731a7012b8f9a40ff831 "$D/safe_cycle_runner.py" | sha256sum -c -
printf '%s  %s\n' 421dc987ac94fcaa716e24aaeda8d34d83afd7088345fd18dc3e70105177495d "$D/policy_r5_fast.py" | sha256sum -c -
"$PY" -B "$D/safe_cycle_runner.py" --round 5 --candidate policy_r5_fast.py --candidate-sha 421dc987ac94fcaa716e24aaeda8d34d83afd7088345fd18dc3e70105177495d --previous policy_r4.py --previous-sha fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa --budget 512 --seeds 28901 28902 28903 --workers 2
echo E108_RANDOM_ROUND5_DONE
