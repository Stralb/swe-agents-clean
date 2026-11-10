#!/bin/bash
#SBATCH --job-name=arc3pubrlsurvey
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
BASE="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arc3_public_rl_survey_20261026"
mkdir -p "$BASE"
CLI="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/n117_kaggle_20261026_prep1/work/.venv/bin/kaggle"
TOKEN="/home-mscluster/astrauss/.kaggle/access_token"
test -s "$TOKEN"
export KAGGLE_API_TOKEN="$(tr -d '\r\n' < "$TOKEN")"
mkdir -m 700 "$BASE/home"
export HOME="$BASE/home"
export XDG_CONFIG_HOME="$HOME/.config"
export KAGGLE_CONFIG_DIR="$HOME/.config/kaggle"
echo "KERNELS_LIST_HELP"
"$CLI" kernels list --help | head -n 85
echo "KERNELS_LIST_ARC_AGI3"
"$CLI" kernels list -s "arc-agi-3" -p 1 --csv | head -n 45
echo "KERNELS_LIST_GOOS"
"$CLI" kernels list -s "stochastic goose" -p 1 --csv | head -n 25
echo "DONE"
