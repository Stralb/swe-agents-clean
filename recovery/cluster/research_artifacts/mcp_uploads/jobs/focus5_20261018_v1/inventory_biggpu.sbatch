#!/bin/bash
#SBATCH --job-name=O5preflight
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/focus5_20261018_v1/inventory.py"
