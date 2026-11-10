#!/bin/bash
#SBATCH --job-name=e126-recheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:45:00
#SBATCH --array=0-5
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
E121=$ROOT/click_diversity_e121_20261026
SCRIPT=$ROOT/click_hybrid_e126_20261026/run_e126.py
OUT=$ROOT/e126_independent_recheck_20261027/fresh
export PYTHONPATH="$E121/runtime/python_site"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
i=$SLURM_ARRAY_TASK_ID
seed=$((79+i/2))
if ((i%2==0)); then arm=baseline; else arm=hybrid_trained; fi
"$PY" -m py_compile "$SCRIPT"
"$PY" "$SCRIPT" --arm "$arm" --seed "$seed" --out "$OUT"
echo "FRESH_E126_DONE seed=$seed arm=$arm"
