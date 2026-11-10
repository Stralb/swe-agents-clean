#!/bin/bash
#SBATCH --job-name=arc3n117status
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
TMP="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_status1/private_home"
mkdir -m 700 "$TMP"
export HOME="$TMP"
export XDG_CONFIG_HOME="$TMP/.config"
export KAGGLE_CONFIG_DIR="$TMP/.config/kaggle"
echo NOTEBOOK_STATUS
"$ROOT/.venv/bin/kaggle" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo NOTEBOOK_LOG_TAIL
"$ROOT/.venv/bin/kaggle" kernels logs arnostrauss/arc-agi-3-n117-local-effect-20261026 | tail -n 70
