#!/bin/bash
#SBATCH --job-name=O5envprobe
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=3G
#SBATCH --time=00:12:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v2/envprobe.py"
