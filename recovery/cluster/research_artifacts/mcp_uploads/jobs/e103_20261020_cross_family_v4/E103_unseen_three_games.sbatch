#!/bin/bash
#SBATCH --job-name=E103_cross_game_frozen
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:25:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e103_20261020_cross_family_v4/E103_cross_game_eval_v2.py
printf '%s  %s\n' e49ed3ff37a50cedd32959ba4e815d7d379eab1d83f378efeabdf4414b88520f "$SRC" | sha256sum -c -
OUT="/home-mscluster/astrauss/e103_cross_family_holdout/E103_three_game_frozen_${SLURM_JOB_ID}"
"$PY" -B "$SRC" --out "$OUT"
echo "E103_EVALUATION_REPORT_LOCATION=$OUT/E103_ALL_GAME_RESULTS.json"