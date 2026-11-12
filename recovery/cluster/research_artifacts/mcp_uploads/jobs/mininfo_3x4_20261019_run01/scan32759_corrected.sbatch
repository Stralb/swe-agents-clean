#!/bin/bash
#SBATCH --job-name=mininfo_32759
#SBATCH --partition=batch
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=00:20:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/mininfo_3x4_20261019_run01/scan32759_corrected.py"
