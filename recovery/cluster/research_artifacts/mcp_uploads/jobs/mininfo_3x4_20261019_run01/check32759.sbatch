#!/bin/bash
#SBATCH --job-name=mininfo_hash
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/mininfo_3x4_20261019_run01/check32759.py"
