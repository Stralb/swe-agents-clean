#!/bin/bash
#SBATCH --job-name=e122nativefull
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_feedback_e122_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
for arm in baseline feedback_rescue_all feedback_rescue_l2 local_credit_l2 rescue_credit_l2; do
 echo START_ARM "$arm"
 "$PY" "$ROOT/run_e122.py" --arm "$arm" --seed 76 --out "$ROOT/results" --resume
 echo DONE_ARM "$arm"
done
echo E122_125_NATIVE_EPISODES_DONE
