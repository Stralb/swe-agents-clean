#!/bin/bash
#SBATCH --job-name=HIST668Acceptance
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=3
#SBATCH --mem=18G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export PYTHONUNBUFFERED=1
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v8/verify668_historical.py"
