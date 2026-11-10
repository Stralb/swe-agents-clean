#!/bin/bash
#SBATCH --job-name=onezip7_context
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_onezip_20261020/build_ready.py"
