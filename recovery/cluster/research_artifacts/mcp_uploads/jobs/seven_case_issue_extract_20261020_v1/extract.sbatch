#!/bin/bash
#SBATCH --job-name=seven_issue_texts
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_issue_extract_20261020_v1/extract.py"
