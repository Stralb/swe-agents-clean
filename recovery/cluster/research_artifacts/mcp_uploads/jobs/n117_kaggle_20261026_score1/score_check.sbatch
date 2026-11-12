#!/bin/bash
#SBATCH --job-name=arc3n117score
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_score1"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$OUT/isolated_home"
export HOME="$OUT/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" competitions submission 57671938
echo "SUBMISSION_STATUS_CHECK_COMPLETE"
