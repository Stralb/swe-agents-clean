#!/bin/bash
#SBATCH --job-name=issue_ablation_intake
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/issue_ablation_two_cases_20261019/intake.py"
