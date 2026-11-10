#!/bin/bash
#SBATCH --job-name=E102_stage4_precond
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e102_20261020_prerequisite_probe/E102_lab_probe.py
printf '%s  %s\n' 5bd36214156bca5bbd535a32fd177a1f4c07601a883984020846faf060c9f789 "$SRC" | sha256sum -c -
"$PY" -B "$SRC"
echo E102_STAGE4_CAUSAL_PRECONDITION_COMPLETE