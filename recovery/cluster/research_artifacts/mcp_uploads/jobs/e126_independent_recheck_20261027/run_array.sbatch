#!/bin/bash
#SBATCH --job-name=e126-fresh-paired
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:45:00
#SBATCH --array=0-5
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/task_%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/task_%A_%a.err
set -euo pipefail
umask 077
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
SCRIPT=$ROOT/click_hybrid_e126_20261026/run_e126.py
OUT=$ROOT/e126_independent_recheck_20261027/fresh
i=$SLURM_ARRAY_TASK_ID
seed=$((79+i/2))
if ((i%2==0)); then arm=baseline; else arm=hybrid_trained; fi
python3 -m py_compile "$SCRIPT"
python3 "$SCRIPT" --arm "$arm" --seed "$seed" --out "$OUT"
echo "FRESH_E126_DONE seed=$seed arm=$arm"
