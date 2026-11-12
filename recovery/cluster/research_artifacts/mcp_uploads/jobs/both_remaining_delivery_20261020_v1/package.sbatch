#!/bin/bash
#SBATCH --job-name=two_negative_zip
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/both_remaining_delivery_20261020_v1/package.py"
