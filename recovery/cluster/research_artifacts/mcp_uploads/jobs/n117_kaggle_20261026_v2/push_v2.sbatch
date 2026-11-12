#!/bin/bash
#SBATCH --job-name=arc3n117pushv2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_v2
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
CLI="$ROOT/.venv/bin/kaggle"
test -s "$TOKEN"
test "$(sha256sum "$BASE/kernel/submission.ipynb" | awk '{print $1}')" = "fa080512b18936a8f9156b22530dbb4cad08e8594759a91fc103b2606767f48b"
test -s "$BASE/kernel/kernel-metadata.json"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/isolated_push_home"
export HOME="$BASE/isolated_push_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "BEFORE_SUBMISSION_STATE"
"$CLI" competitions submission 57671938 || true
echo "PUSH_CORRECTED_N117_NOTEBOOK"
"$CLI" kernels push -p "$BASE/kernel"
echo "PUSH_RETURNED"
"$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
echo "PUSH_JOB_FINISHED_NO_OFFICIAL_COMPETITION_SUBMISSION"