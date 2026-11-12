#!/bin/bash
#SBATCH --job-name=case32759_F013
#SBATCH --partition=batch
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=00:30:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/case32759_issue_anchor_f0123_20261019/scan_F.py"
