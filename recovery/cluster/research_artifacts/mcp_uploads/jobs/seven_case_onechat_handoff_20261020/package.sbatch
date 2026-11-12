#!/bin/bash
#SBATCH --job-name=seven_case_handoff
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:15:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_onechat_handoff_20261020/create_support.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_onechat_handoff_20261020/build.py"
