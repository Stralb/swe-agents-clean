#!/bin/bash
#SBATCH --job-name=final_seven_handoff
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:20:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/SEVEN_HANDOFF_20261020_DOCS_v1/docs.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/SEVEN_HANDOFF_20261020_BUILD_v1/build.py"
