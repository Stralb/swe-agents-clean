#!/bin/bash
#SBATCH --job-name=E096_greedy_replica
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e093_20261020_online_hypothesis
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' d27469802f40beb019e62c7412f51bc80f668a51305a664eff0bfaad750f8786 "$D/E093_native_runner_v0.py" | sha256sum -c -
for SEED in 28902 28903;do
 OUT="/home-mscluster/astrauss/e093_from_reset_research/E096_greedy_replica_seed${SEED}_${SLURM_JOB_ID}"
 "$PY" -B "$D/E093_native_runner_v0.py" --seed "$SEED" --budget 160 --env-seed 0 --mode full --out "$OUT"
 echo "E096_SAME_SEED_GREEDY_RESULT $SEED $OUT/E093_REPORT.json"
done
echo E096_GREEDY_REPLICATION_DONE