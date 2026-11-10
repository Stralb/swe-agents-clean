#!/bin/bash
#SBATCH --job-name=e123l1seeds
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:35:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
for seed in 77 78; do
 for arm in baseline l1_d14_salience l1_random_prior l1_trained_prior; do
  echo "BEGIN $seed $arm"
  "$PY" "$ROOT/run_e123_l1_v2.py" --arm "$arm" --seed "$seed" --out "$ROOT/level1" --resume
  echo "END $seed $arm"
 done
done
echo E123_L1_SEEDS77_78_COMPLETE
