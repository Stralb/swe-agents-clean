#!/bin/bash
#SBATCH --job-name=e125smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:16:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/sparse_click_transfer_e125_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
"$PY" -m py_compile "$ROOT/run_e125.py"
for arm in baseline sparse80_trained sparse70_trained sparse80_random sparse80_salience; do
 "$PY" "$ROOT/run_e125.py" --arm "$arm" --seed 76 --games s5i5 r11l vc33 tn36 --out "$ROOT/smoke"
done
echo E125_SMOKE_COMPLETE
