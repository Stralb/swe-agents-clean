#!/bin/bash
#SBATCH --job-name=arc3n117check1816
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:06:00
set -euo pipefail
umask 077
ROOT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work"
BASE="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_check_1816"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
CLI="$ROOT/.venv/bin/kaggle"
test -s "$TOKEN"
test -x "$CLI"
mkdir -m 700 "$BASE/isolated_home"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
export HOME="$BASE/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "=== OFFICIAL SUBMISSION 57671938 ==="
"$CLI" competitions submission 57671938 || true
echo "=== RECENT ARC-AGI-3 SUBMISSIONS ==="
"$CLI" competitions submissions -c arc-prize-2026-arc-agi-3 || true
echo "=== NOTEBOOK STATUS ==="
"$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026 || true
echo "=== PRIVATE DATASET STATUS ==="
"$CLI" datasets status arnostrauss/arc-agi-3-n117-agent-source-20261026 || true
echo "=== NOTEBOOK LOGS ==="
"$CLI" kernels logs arnostrauss/arc-agi-3-n117-local-effect-20261026 | tail -n 90 || true
echo "=== READ ONLY COMPLETE ==="