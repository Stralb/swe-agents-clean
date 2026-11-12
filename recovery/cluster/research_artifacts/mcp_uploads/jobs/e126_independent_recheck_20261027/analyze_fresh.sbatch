#!/bin/bash
#SBATCH --job-name=e126-fresh-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
#SBATCH --dependency=afterok:76132
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/analyze_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027/analyze_%j.err
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_independent_recheck_20261027
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" -m py_compile "$ROOT/analyze_fresh.py"
"$PY" "$ROOT/analyze_fresh.py"
