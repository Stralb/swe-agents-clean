#!/bin/bash
#SBATCH --job-name=seven_scan_archive_v2
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_new_scans_20261020_v2/aggregate.py"
