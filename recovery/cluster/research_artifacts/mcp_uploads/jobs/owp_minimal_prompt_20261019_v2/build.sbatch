#!/bin/bash
#SBATCH --job-name=owp_min3x4
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_minimal_prompt_20261019_v2/build.py"
