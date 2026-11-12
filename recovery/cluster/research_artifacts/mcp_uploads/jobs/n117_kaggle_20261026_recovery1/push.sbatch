#!/bin/bash
#SBATCH --job-name=arc3n117recoverypush
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=2G
#SBATCH --time=00:15:00
set -euo pipefail
umask 077
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_recovery1
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
CLI="$ROOT/.venv/bin/kaggle"
test -s "$TOKEN"
test "$(sha256sum "$BASE/kernel/submission.ipynb" | awk '{print $1}')" = "68305ce3971b5e9771de5d59b5d906a7d11e78e3213b3a6b8d191380a92ed6d7"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/kaggle_home_push"
export HOME="$BASE/kaggle_home_push"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "VERIFY_DATASET"
"$CLI" datasets status arnostrauss/arc-agi-3-n117-agent-source-20261026
echo "PUSH_FRESH_KERNEL"
"$CLI" kernels push -p "$BASE/kernel"
echo "KERNEL_PUSH_FINISHED"
"$CLI" kernels status arnostrauss/arc-agi-3-n117-recovery-20261026
echo "NO_OFFICIAL_COMPETITION_SUBMISSION_SPENT"
