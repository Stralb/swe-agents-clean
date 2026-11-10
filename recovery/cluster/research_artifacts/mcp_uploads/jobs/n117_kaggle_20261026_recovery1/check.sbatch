#!/bin/bash
#SBATCH --job-name=arc3n117recoverycheck
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_recovery1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
CLI="$ROOT/.venv/bin/kaggle"
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/kaggle_home_check"
export HOME="$BASE/kaggle_home_check"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo KERNEL_STATUS
"$CLI" kernels status arnostrauss/arc-agi-3-n117-recovery-20261026
echo KERNEL_LOGS
"$CLI" kernels logs arnostrauss/arc-agi-3-n117-recovery-20261026 | tail -n 45
echo KERNEL_OUTPUT
mkdir -m 700 "$BASE/preview_output"
"$CLI" kernels output arnostrauss/arc-agi-3-n117-recovery-20261026 -p "$BASE/preview_output"
echo OUTPUT_FILES
find "$BASE/preview_output" -maxdepth 1 -type f -printf '%f %s bytes\n'
test -s "$BASE/preview_output/submission.parquet"
echo PREVIEW_PARQUET_PRESENT
