#!/bin/bash
#SBATCH --job-name=E087_causal_replan
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e087_20261019_replanning/E087_replan_v0.py
printf '%s  %s\n' a71d09eb2a55e641b8bfae645d3c77991d81f7b07e54f38052ca75913ee78899 "$SRC" | sha256sum -c -
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python -B "$SRC"
echo E087_NATIVE_CONTROLLED_REPLAN_FINISHED