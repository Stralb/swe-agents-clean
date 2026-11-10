#!/bin/bash
#SBATCH --job-name=E085_operator_algebra
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e085_20261019_operator_algebra/E085_algebra_v0.py
printf '%s  %s\n' 55bbd55fe86a4982f5dfe7a314eaf5eef9d05a80d3fba3ff45875e824b913e5e "$SRC" | sha256sum -c -
"$PY" -B "$SRC"
echo E085_BLACKBOX_CAUSAL_ALGEBRA_DONE