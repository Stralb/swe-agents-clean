#!/bin/bash
#SBATCH --job-name=arc3n117diagv2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_diagnose_v2_1
CLI="$ROOT/.venv/bin/kaggle"
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/isolated_home"
export HOME="$BASE/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "=== Kaggle submission V2 ==="
"$CLI" competitions submission 57672825 || true
echo "=== Kaggle submission V1 ==="
"$CLI" competitions submission 57671938 || true
echo "=== All current competition submissions ==="
"$CLI" competitions submissions -c arc-prize-2026-arc-agi-3 || true
echo "=== Notebook status ==="
"$CLI" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026 || true
echo "=== Kaggle CLI version ==="
"$CLI" --version
echo "=== V2 source, metadata SHA-256 and size ==="
sha256sum /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_v2/kernel/{submission.ipynb,kernel-metadata.json}
wc -c /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_v2/kernel/{submission.ipynb,kernel-metadata.json}
echo "=== Done ==="
