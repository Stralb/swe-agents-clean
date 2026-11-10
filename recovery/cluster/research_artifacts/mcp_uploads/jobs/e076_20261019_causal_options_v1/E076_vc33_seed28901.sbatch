#!/bin/bash
#SBATCH --job-name=E076_vc33_one_seed
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e076_20261019_causal_options_v1/E076_causal_options_v1.py
printf '%s  %s\n' 8b0f0b4873e39d103fcb3754e04f82b42d4f279df3d586b3625ec797131166b4 "$SRC" | sha256sum -c -
mkdir -p /home-mscluster/astrauss/e076_one_game_runs
"$PY" -B "$SRC" --seed 28901 --env-seed 0 --budget 160 --out "/home-mscluster/astrauss/e076_one_game_runs/E076_VC33_${SLURM_JOB_ID}_seed28901"
echo E076_NATIVE_DEV_COMPARISON_COMPLETED