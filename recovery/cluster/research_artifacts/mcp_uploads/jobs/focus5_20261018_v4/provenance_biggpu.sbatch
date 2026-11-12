#!/bin/bash
#SBATCH --job-name=O5IssueProvenance
#SBATCH --partition=biggpu
#SBATCH --dependency=afterany:70994
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v4/provenance_v2.py"
