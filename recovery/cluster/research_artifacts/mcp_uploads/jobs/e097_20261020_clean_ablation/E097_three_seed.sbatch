#!/bin/bash
#SBATCH --job-name=E097_clean_ablation
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e097_20261020_clean_ablation
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' eba2e2048ec85e738048e505203fcbe5577550d01663c9e20dfdf48fb8078421 "$D/E097_clean_core_v2.py" | sha256sum -c -
printf '%s  %s\n' 61530ff6ef8c426b6cc0484e0eb61ca52a83a7ca6861bfe1c7caedbb3e19f62a "$D/E097_native_runner_v2.py" | sha256sum -c -
"$PY" -B "$D/E097_native_runner_v2.py" --self-test
for SEED in 28901 28902 28903;do
 OUT="/home-mscluster/astrauss/e097_clean_mechanistic_ablation/E097_seed${SEED}_${SLURM_JOB_ID}"
 echo "E097_CLEAN_SEED_BEGIN $SEED"
 "$PY" -B "$D/E097_native_runner_v2.py" --seed "$SEED" --budget 160 --env-seed 0 --mode full no_memory no_causal no_goal frozen_repeat --out "$OUT"
 echo "E097_CLEAN_SEED_END $SEED $OUT/E097_REPORT.json"
done
echo E097_FULLY_ORTHOGONAL_ABLATIONS_COMPLETE