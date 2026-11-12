#!/bin/bash
#SBATCH --job-name=arc3n117v2check
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_v2
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/isolated_check_home"
export HOME="$BASE/isolated_check_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
CLI="$ROOT/.venv/bin/kaggle"
echo "NOTEBOOK_STATUS"
"$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo "NOTEBOOK_LOGS"
"$CLI" kernels logs arnostrauss/arc-agi-3-n117-local-effect-20261026 | tail -n 75
echo "NO_COMPETITION_SUBMISSION_MADE"