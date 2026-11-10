#!/bin/bash
#SBATCH --job-name=seven_repair_archive
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_targeted_final_20261020_v1/package.py"
