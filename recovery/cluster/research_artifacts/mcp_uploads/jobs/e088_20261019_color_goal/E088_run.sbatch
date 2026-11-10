#!/bin/bash
#SBATCH --job-name=E088_colour_goal
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e088_20261019_color_goal/E088_visual_goal_v0.py
printf '%s  %s\n' e37c3c77c85cdb3f07b72070bacdcc1d80b71fe60f86a5256d03b1866b818062 "$SRC" | sha256sum -c -
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python -B "$SRC"
echo E088_COLOUR_GOAL_RESEARCH_RUN_ENDED