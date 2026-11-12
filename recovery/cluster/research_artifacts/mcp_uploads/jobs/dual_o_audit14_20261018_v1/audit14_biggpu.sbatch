#!/bin/bash
#SBATCH --job-name=dualO14_audit
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/dual_o_audit14_20261018_v1/audit14.py"
