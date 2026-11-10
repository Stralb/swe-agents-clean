#!/bin/bash
#SBATCH --job-name=e123consmoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/teammate_prior_e123_20261026
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
"$PY" -m py_compile "$ROOT/run_e123_conservative.py"
for arm in baseline confidence_trained confidence_random; do
 "$PY" "$ROOT/run_e123_conservative.py" --arm "$arm" --games s5i5 tn36 lf52 dc22 --seed 76 --out "$ROOT/conservative_smoke"
done
echo E123_CONFIDENCE_SMOKE_COMPLETE
