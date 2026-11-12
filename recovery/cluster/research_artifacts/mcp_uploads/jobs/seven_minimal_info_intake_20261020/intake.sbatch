#!/bin/bash
#SBATCH --job-name=sev_min_intake
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_minimal_info_intake_20261020/intake.py"
