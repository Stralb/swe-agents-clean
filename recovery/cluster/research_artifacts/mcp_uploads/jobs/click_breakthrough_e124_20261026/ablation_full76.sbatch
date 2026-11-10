#!/bin/bash
#SBATCH --job-name=e124ablate25
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:25:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_breakthrough_e124_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
for arm in contingency rarity_only effect_only random_bonus; do
 echo "BEGIN $arm"
 "$PY" "$ROOT/run_e124_ablation.py" --arm "$arm" --seed 76 --out "$ROOT/ablation" --resume
 echo "DONE $arm"
done
echo E124_ABLATION_ALL_100_DONE
