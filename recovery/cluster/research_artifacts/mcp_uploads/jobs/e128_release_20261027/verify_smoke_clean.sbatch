#!/bin/bash
#SBATCH --job-name=e128cleanverify
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
cd /tmp
E121=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
export PYTHONPATH="$E121/runtime/python_site"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=''
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" -c 'import runpy;runpy.run_path("/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/verify_release.py",run_name="__main__")'
echo E128_SMOKE_PARITY_COMPLETE
