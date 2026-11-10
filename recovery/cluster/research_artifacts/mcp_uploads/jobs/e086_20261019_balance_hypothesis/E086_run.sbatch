#!/bin/bash
#SBATCH --job-name=E086_goal_balance
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e086_20261019_balance_hypothesis/E086_balance_v0.py
printf '%s  %s\n' bb17af2aae384ad03ac162a7d836663298c8ecf2f90378eb53a0a5737fb7c7f9 "$SRC" | sha256sum -c -
"$PY" -B "$SRC"
echo E086_GOAL_HYPOTHESIS_FROZEN