#!/bin/bash
#SBATCH --job-name=e121seedchecks
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
for seed in 77 78; do
  for arm in baseline l2_diverse2; do
    echo "BEGIN seed $seed arm $arm"
    "$PY" "$BASE/run_e121_staged.py" --arm "$arm" --out "$BASE/seed_checks/seed$seed" --policy-seed "$seed" --native-seed 47 --resume
    echo "END seed $seed arm $arm"
  done
done
echo E121_SEED_ABLATIONS_FINISHED
