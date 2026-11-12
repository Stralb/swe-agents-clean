#!/bin/bash
#SBATCH --job-name=arc3n117submitv2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_v2
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
CLI="$ROOT/.venv/bin/kaggle"
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
test "$(sha256sum "$BASE/kernel/submission.ipynb" | awk '{print $1}')" = "fa080512b18936a8f9156b22530dbb4cad08e8594759a91fc103b2606767f48b"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/isolated_submit_home"
export HOME="$BASE/isolated_submit_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
PREVIOUS="$("$CLI" competitions submission 57671938)"
echo "$PREVIOUS"
echo "$PREVIOUS" | grep -Eq 'Status:[[:space:]]+ERROR' || { echo "ABORT_PREVIOUS_NOT_ERROR"; exit 5; }
NOTEBOOK="$("$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026)"
echo "$NOTEBOOK"
echo "$NOTEBOOK" | grep -q 'COMPLETE' || { echo "ABORT_NOTEBOOK_NOT_COMPLETE"; exit 6; }
mkdir -m 700 "$BASE/v2_output"
"$CLI" kernels output arnostrauss/arc-agi-3-n117-local-effect-20261026 -p "$BASE/v2_output"
test -s "$BASE/v2_output/submission.parquet" || { echo "ABORT_MISSING_PREVIEW_PARQUET"; exit 7; }
echo "NOTEBOOK_PREVIEW_PARQUET_PRESENT"
echo "SUBMITTING_OFFICIAL_VERSION_2"
"$CLI" competitions submit -c arc-prize-2026-arc-agi-3 -f submission.parquet -k arnostrauss/arc-agi-3-n117-local-effect-20261026 -v 2 -m "N117 v2: competition-only dependency install; frozen model unchanged"
echo "OFFICIAL_VERSION_2_SUBMIT_COMMAND_SUCCEEDED"
