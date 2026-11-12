#!/bin/bash
#SBATCH --job-name=e126prep2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_kaggle_submit_20261027/preflight2_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e126_kaggle_submit_20261027/preflight2_%j.err
set -euo pipefail
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs
KG=$ROOT/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
echo KAGGLE_VERS
"$KG" --version
echo KAGGLE_PUSH_HELP
"$KG" kernels push --help | head -42
echo KAGGLE_SUBMIT_HELP
"$KG" competitions submit --help | head -55
echo KAGGLE_LIST
"$KG" kernels list -m --page-size 15 | head -30 || true
echo KAGGLE_SUBMISSIONS
"$KG" competitions submissions -c arc-prize-2026-arc-agi-3 | head -28 || true
echo RELATED
for d in "$ROOT"/e128* "$ROOT"/*kaggle* "$ROOT"/*release*; do if test -d "$d"; then echo "$(basename "$d")"; fi; done
echo E126_PREFLIGHT_COMPLETE
