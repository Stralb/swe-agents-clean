#!/bin/bash
#SBATCH --job-name=histPR14_preflight
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/historical_pr_apply14_20261018_v1/hist_apply14.py"
