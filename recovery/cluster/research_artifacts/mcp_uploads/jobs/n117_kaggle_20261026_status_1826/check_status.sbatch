#!/bin/bash
#SBATCH --job-name=arc3status1826
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
CLI=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle
TOKEN=/home-mscluster/astrauss/.kaggle/access_token
BASE=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_status_1826
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/home"
export HOME="$BASE/home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo CHECK_SUBMISSION_57671938
"$CLI" competitions submission 57671938
echo CHECK_DONE
