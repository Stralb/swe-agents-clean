#!/bin/bash
#SBATCH --job-name=E078_frozen_model_read
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
echo "====== src/adapter.py: interface ======"
sed -n '1,240p' "$P/src/adapter.py"
echo "====== src/model.py: network ======"
sed -n '1,240p' "$P/src/model.py"
echo "====== src/synthetic.py: possible tests ======"
sed -n '1,150p' "$P/src/synthetic.py"
echo "====== code evaluator scripts ======"
find "$P/scripts" -maxdepth 1 -name '*framework*' -o -name '*train*' -o -name '*eval*'
echo "====== code read complete ======"