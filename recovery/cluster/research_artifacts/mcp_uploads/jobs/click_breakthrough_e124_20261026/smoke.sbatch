#!/bin/bash
#SBATCH --job-name=e124smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_breakthrough_e124_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
"$PY" -m py_compile "$ROOT/run_e124.py"
for arm in baseline prune_bg prune_broad edge_contact contingency selection_chain; do
 "$PY" "$ROOT/run_e124.py" --arm "$arm" --seed 76 --games s5i5 vc33 lf52 --out "$ROOT/smoke"
done
echo E124_SMOKE_COMPLETE
