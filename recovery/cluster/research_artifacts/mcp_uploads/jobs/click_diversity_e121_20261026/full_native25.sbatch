#!/bin/bash
#SBATCH --job-name=e121native25
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$BASE/runtime/python_site"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=''
for arm in baseline near2 diverse2 diverse3; do
 echo "BEGIN_ARM $arm"
 "$PY" "$BASE/run_e121.py" --arm "$arm" --out "$BASE/results" --resume
 echo "END_ARM $arm"
done
echo "E121_100_NATIVE_EPISODES_COMPLETE"
