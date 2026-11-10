#!/bin/bash
#SBATCH --job-name=E075_native_contract
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "=== ArcSession API ==="
sed -n '140,425p' "$P/src/adapter.py"
echo "=== Native output contracts ==="
sed -n '1,95p' "$P/src/e027/reproducibility.py"
echo "END"