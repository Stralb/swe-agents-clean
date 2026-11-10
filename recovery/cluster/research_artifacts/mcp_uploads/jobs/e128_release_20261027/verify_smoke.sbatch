#!/bin/bash
#SBATCH --job-name=e128smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=7G
#SBATCH --time=00:18:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" -m py_compile "$ROOT/verify_release.py"
"$PY" "$ROOT/verify_release.py"
echo E128_SMOKE_JOB_COMPLETE
