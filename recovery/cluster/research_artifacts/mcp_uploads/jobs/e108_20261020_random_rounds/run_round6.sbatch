#!/bin/bash
#SBATCH --job-name=E108_random5_round6
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:40:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
P=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e106_20261020_general_agent
export PYTHONPATH="$D:$P"
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' b8557fe8fae6d6afe5f10767fe509607ea41e4828ffdb1c855bd4077c6fc3d70 "$D/policy_r6.py" | sha256sum -c -
printf '%s  %s\n' 5db4392d135eb08e736609f77c92b5fa431af0ba419b731a7012b8f9a40ff831 "$D/safe_cycle_runner.py" | sha256sum -c -
"$PY" -B "$D/safe_cycle_runner.py" --round 6 --candidate policy_r6.py --candidate-sha b8557fe8fae6d6afe5f10767fe509607ea41e4828ffdb1c855bd4077c6fc3d70 --previous policy_r5_fast.py --previous-sha 421dc987ac94fcaa716e24aaeda8d34d83afd7088345fd18dc3e70105177495d --budget 512 --seeds 28901 28902 28903 --workers 2
echo E108_RANDOM_ROUND6_DONE
