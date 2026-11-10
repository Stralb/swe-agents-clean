#!/bin/bash
#SBATCH --job-name=e121l2only
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:30:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$BASE/runtime/python_site"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=''
for arm in l2_near2 l2_diverse2 l2_diverse3; do
  echo "BEGIN_ARM $arm"
  "$PY" "$BASE/run_e121_staged.py" --arm "$arm" --out "$BASE/results" --resume
  echo "END_ARM $arm"
done
echo E121_ALL_GATED_ARM_EPISODES_COMPLETE
