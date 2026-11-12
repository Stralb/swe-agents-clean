#!/bin/bash
#SBATCH --job-name=rlpaper-kaggle
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo "ARC_AGI3_OFFICIAL_KAGGLE_SUBMISSIONS_READONLY"
"$KG" competitions submissions -c arc-prize-2026-arc-agi-3
echo "ARC_KAGGLE_AUDIT_DONE"
