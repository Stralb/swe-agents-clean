#!/bin/bash
#SBATCH --job-name=OWP14_target_idx
#SBATCH --partition=biggpu
#SBATCH --dependency=afterany:71017
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_20261018_v2/target_index_fix.py"
