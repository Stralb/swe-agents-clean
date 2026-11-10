#!/bin/bash
#SBATCH --job-name=E080_native_replicate
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:25:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e080_20261019_online_rl_options/E080_native_option_prior_v0.py
printf '%s  %s\n' 60c64687a4eed82dd3c0ed776241c65c43c2f945988e76ecb96a05bd0f40e7fd "$SRC" | sha256sum -c -
for SEED in 28902 28903; do
 OUT="/home-mscluster/astrauss/e080_course_development/E080_native_seed${SEED}_${SLURM_JOB_ID}"
 echo "E080_REPLICATION_BEGIN seed=$SEED"
 "$PY" -B "$SRC" --seed "$SEED" --budget 160 --out "$OUT"
 echo "E080_REPLICATION_COMPLETE seed=$SEED report=$OUT/E080_RESULTS.json"
done
echo E080_TWO_FRESH_SEEDS_COMPLETED