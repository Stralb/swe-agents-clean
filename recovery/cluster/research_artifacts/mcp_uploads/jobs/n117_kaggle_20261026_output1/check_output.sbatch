#!/bin/bash
#SBATCH --job-name=arc3n117files
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
OUT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_output1"
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$OUT/isolated_home"
mkdir -m 700 "$OUT/output"
export HOME="$OUT/isolated_home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
"$ROOT/.venv/bin/kaggle" kernels status arnostrauss/arc-agi-3-n117-local-effect-20261026
"$ROOT/.venv/bin/kaggle" kernels output arnostrauss/arc-agi-3-n117-local-effect-20261026 -p "$OUT/output"
echo OUTPUT_FILES
find "$OUT/output" -type f -printf '%P %s bytes\n'
if [ -s "$OUT/output/submission.parquet" ]; then echo SUBMISSION_PARQUET_PRESENT; else echo SUBMISSION_PARQUET_MISSING; exit 4; fi
