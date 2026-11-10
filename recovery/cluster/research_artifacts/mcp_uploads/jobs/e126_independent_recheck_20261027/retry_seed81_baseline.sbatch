#!/bin/bash
#SBATCH --job-name=e126-b81-retry
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/retry_81_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/retry_81_%j.err
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
export PYTHONPATH="$ROOT/click_diversity_e121_20261026/runtime/python_site"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=""
"$PY" "$ROOT/click_hybrid_e126_20261026/run_e126.py" --arm baseline --seed 81 --out "$ROOT/e126_independent_recheck_20261027/fresh"
echo "E126_SEED81_BASELINE_RETRY_COMPLETE"
