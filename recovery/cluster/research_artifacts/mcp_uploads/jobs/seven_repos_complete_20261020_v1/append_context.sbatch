#!/bin/bash
#SBATCH --job-name=seven_full_context
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_repos_complete_20261020_v1/append_context.py"
