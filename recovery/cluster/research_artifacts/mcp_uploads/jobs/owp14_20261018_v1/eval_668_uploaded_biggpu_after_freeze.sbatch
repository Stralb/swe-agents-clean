#!/bin/bash
#SBATCH --job-name=OWP668_evaluate
#SBATCH --partition=biggpu
#SBATCH --dependency=afterany:71014
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_20261018_v1/eval_668_uploaded.py"
