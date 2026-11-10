#!/bin/bash
#SBATCH --job-name=v0-v1-smoke
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=4
#SBATCH --time=01:00:00
#SBATCH --output=logs/v0_v1_smoke_%j.out
#SBATCH --error=logs/v0_v1_smoke_%j.err

set -euo pipefail

cd /home-mscluster/astrauss/RL-ARC-AGI-3-Project
source /home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/activate

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1

bash scripts/compare_dqn_baselines.sh \
  "ls20,sp80,cd82,r11l,tn36" \
  200 \
  "5209"
