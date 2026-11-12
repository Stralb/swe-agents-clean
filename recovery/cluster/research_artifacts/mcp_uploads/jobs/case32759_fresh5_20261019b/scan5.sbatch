#!/bin/bash
#SBATCH --job-name=c32759_fresh5
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/case32759_fresh5_20261019b/scan5.py"
