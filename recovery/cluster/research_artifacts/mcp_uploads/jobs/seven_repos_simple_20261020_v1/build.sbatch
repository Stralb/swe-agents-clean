#!/bin/bash
#SBATCH --job-name=seven_frozen_zip
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_repos_simple_20261020_v1/build.py"
