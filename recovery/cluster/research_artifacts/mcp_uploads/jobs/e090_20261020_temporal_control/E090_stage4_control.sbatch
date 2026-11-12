#!/bin/bash
#SBATCH --job-name=E090_temporal_causality
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e090_20261020_temporal_control/E090_stage4_control_v0.py
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' 08c8e7f5db0cc53d767a029df302ac850eb1c176d7820328597ea657446ef63d "$SRC" | sha256sum -c -
"$PY" -B "$SRC"
echo E090_NATIVE_TEMPORAL_CAUSAL_RESEARCH_COMPLETE