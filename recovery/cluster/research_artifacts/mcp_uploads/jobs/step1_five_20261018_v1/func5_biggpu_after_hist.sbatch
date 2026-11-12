#!/bin/bash
#SBATCH --job-name=O5functional
#SBATCH --partition=biggpu
#SBATCH --array=0-9%1
#SBATCH --dependency=afterany:70972
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/step1_five_20261018_v1/func5.py"
