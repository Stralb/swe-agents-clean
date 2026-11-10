#!/bin/bash
#SBATCH --job-name=two_contracts
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:10:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/remaining2_study_20261020_v1/inspect.py"
