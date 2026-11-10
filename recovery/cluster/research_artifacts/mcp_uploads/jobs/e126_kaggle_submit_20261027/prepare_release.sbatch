#!/bin/bash
#SBATCH --job-name=e126build
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_kaggle_submit_20261027
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" -m py_compile "$ROOT/prepare_release.py"
"$PY" "$ROOT/prepare_release.py"
