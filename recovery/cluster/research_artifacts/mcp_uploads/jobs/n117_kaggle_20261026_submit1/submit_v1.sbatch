#!/bin/bash
#SBATCH --job-name=arc3n117submit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_submit1"
test -s "$TOKEN"
test -s "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_output1/output/submission.parquet"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$OUT/isolated_home"
export HOME="$OUT/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo "SUBMITTING_NOTEBOOK_VERSION_1"
"$ROOT/.venv/bin/kaggle" competitions submit arc-prize-2026-arc-agi-3 -f submission.parquet -k arnostrauss/arc-agi-3-n117-local-effect-20261026 -v 1 -m "N117 frozen checkpoint local-effect policy; private source dataset"
echo "OFFICIAL_SUBMIT_COMMAND_SUCCEEDED"
