#!/bin/bash
#SBATCH --job-name=E084_affordance_census
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e084_20261019_bottom_controls/E084_all_controls_v0.py
printf '%s  %s\n' 7e0e8b4b3f5e398a1be04cb1c5cd3ae7b98f24598d9e77140d791fd393f31d75 "$SRC" | sha256sum -c -
OUT="/home-mscluster/astrauss/e084_single_game_causal/E084_vc33_${SLURM_JOB_ID}"
"$PY" -B "$SRC" --max-interventions 25 --out "$OUT"
echo "E084_CAUSAL_CONTROLS_SAVED $OUT"