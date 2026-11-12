#!/bin/bash
#SBATCH --job-name=dualO14_attr
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/dual_o_attr14_20261018_v1/attr14.py"
