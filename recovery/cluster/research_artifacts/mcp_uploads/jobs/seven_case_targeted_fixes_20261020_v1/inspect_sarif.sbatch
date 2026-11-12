#!/bin/bash
#SBATCH --job-name=seven_dataflow
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:10:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_targeted_fixes_20261020_v1/inspect_sarif.py"
