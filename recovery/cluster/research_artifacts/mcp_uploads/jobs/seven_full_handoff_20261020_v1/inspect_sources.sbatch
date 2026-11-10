#!/bin/bash
#SBATCH --job-name=seven_sources_inventory
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:07:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_full_handoff_20261020_v1/inspect_sources.py"
