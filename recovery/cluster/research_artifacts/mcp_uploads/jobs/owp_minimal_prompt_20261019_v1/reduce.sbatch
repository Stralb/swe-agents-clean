#!/bin/bash
#SBATCH --job-name=owp_media_reduce
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_minimal_prompt_20261019_v1/reduce.py"
