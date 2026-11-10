#!/bin/bash
#SBATCH --job-name=E098_new_env_seeds
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e097_20261020_clean_ablation_v3
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' bd30c53e7abe5b63424aec23b949a685822c4ae3c9d89920ab5ed203c199a279 "$D/E097_clean_core_v3.py" | sha256sum -c -
printf '%s  %s\n' 965ba7161af4b25ae4f9b42b9eb44be887380a840f6348da1f9aa3f90210bcac "$D/E097_native_runner_v3.py" | sha256sum -c -
for ENV_SEED in 1 2 3;do
 OUT="/home-mscluster/astrauss/e098_dev_game_seed_robustness/E098_vc33_env${ENV_SEED}_${SLURM_JOB_ID}"
 echo "E098_ENV_SEED_BEGIN $ENV_SEED"
 "$PY" -B "$D/E097_native_runner_v3.py" --seed 28901 --env-seed "$ENV_SEED" --budget 160 --mode full frozen_repeat --out "$OUT"
 echo "E098_ENV_SEED_END $ENV_SEED $OUT/E097_REPORT.json"
done
echo E098_ENV_SEED_STUDY_COMPLETE