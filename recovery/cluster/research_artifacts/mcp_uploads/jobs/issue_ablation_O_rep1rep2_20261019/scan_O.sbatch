#!/bin/bash
#SBATCH --job-name=issue_abl_O
#SBATCH --partition=batch
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=00:25:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/issue_ablation_O_rep1rep2_20261019/scan_O.py"
