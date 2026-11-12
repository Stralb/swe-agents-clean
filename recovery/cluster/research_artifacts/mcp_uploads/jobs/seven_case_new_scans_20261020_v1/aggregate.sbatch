#!/bin/bash
#SBATCH --job-name=seven_scan_archive
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_new_scans_20261020_v1/aggregate.py"
