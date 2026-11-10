#!/bin/bash
#SBATCH --job-name=e126scorecheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo E126_SUBMISSION_57690887_STATUS
"$KG" competitions submissions -c arc-prize-2026-arc-agi-3 | head -10
echo E126_SCORE_STATUS_CHECK_COMPLETE
