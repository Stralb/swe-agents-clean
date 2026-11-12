#!/bin/bash
#SBATCH --job-name=OWPResearchHandoff
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_pilot_handoff_20261018_v1/handoff.py"
