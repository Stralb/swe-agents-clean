#!/bin/bash
#SBATCH --job-name=O5artifactProbe
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=18G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/node24/bin:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export PYTHONUNBUFFERED=1
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v5/query_pins.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v5/run_smoke.py"
