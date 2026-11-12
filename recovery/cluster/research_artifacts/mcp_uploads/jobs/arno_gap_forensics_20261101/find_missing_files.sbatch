#!/bin/bash
#SBATCH --job-name=arno_gap_inventory
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_gap_forensics_20261101"
python3 -B find_missing_files.py
