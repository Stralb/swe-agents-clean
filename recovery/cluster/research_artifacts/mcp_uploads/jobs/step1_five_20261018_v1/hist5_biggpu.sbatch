#!/bin/bash
#SBATCH --job-name=hist5replay
#SBATCH --partition=biggpu
#SBATCH --array=0-4%1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:30:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/step1_five_20261018_v1/hist5.py"
