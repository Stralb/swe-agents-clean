#!/bin/bash
#SBATCH --job-name=issue_ablation_2cases
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:10:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/issue_recipe_two_cases_20261019/build_fixed.py"
