#!/bin/bash
#SBATCH --job-name=E092_stage4_colour_alignment
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e092_20261020_stage4_alignment_lab/E092_stage4_alignment_v0.py
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' bb27b3bf8ef6aed23b45df8e9a4bb054f12ba3bb115afb1bed0e658a89cbd44e "$SRC" | sha256sum -c -
"$PY" -B "$SRC"
echo E092_COMPLETE