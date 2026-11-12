#!/bin/bash
#SBATCH --job-name=E077_vc33_shared
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e077_20261019_shared_affordance/E077_shared_affordance_v0.py
printf '%s  %s\n' ede064bdb72fb632d90d6aec537b7a5f62d74521351cb859453d3ea558bb92c6 "$SRC" | sha256sum -c -
mkdir -p /home-mscluster/astrauss/e077_one_game_runs
"$PY" -B "$SRC" --seed 28901 --env-seed 0 --budget 160 --out "/home-mscluster/astrauss/e077_one_game_runs/E077_VC33_${SLURM_JOB_ID}_seed28901"
echo E077_SHARED_NATIVE_SINGLE_SEED_COMPLETED