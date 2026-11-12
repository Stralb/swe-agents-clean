#!/bin/bash
#SBATCH --job-name=O668FullAcceptance
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=3
#SBATCH --mem=18G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export PYTHONUNBUFFERED=1
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v6/verify668_v2_fixed.py"
