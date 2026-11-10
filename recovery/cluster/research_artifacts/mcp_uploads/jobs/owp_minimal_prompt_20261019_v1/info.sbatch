#!/bin/bash
#SBATCH --job-name=owp_sourceinfo
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_minimal_prompt_20261019_v1/info.py"
