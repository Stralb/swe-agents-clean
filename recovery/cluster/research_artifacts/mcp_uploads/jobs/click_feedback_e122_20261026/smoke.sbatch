#!/bin/bash
#SBATCH --job-name=e122smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_feedback_e122_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
"$PY" -m py_compile "$ROOT/run_e122.py"
for arm in baseline feedback_rescue_all feedback_rescue_l2 local_credit_l2 rescue_credit_l2; do
 "$PY" "$ROOT/run_e122.py" --arm "$arm" --games vc33 dc22 --seed 76 --out "$ROOT/smoke"
done
echo E122_SMOKE_OK
