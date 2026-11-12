#!/bin/bash
#SBATCH --job-name=e121smoke
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/click_diversity_e121_20261026
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
python3 "$BASE/runtime_bootstrap.py" extract
/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python "$BASE/runtime_bootstrap.py" smoke
echo E121_SMOKE_COMPLETED
