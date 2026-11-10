#!/bin/bash
#SBATCH --job-name=codex_shellfree_r02
#SBATCH --partition=batch
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=00:25:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/case32759_shellfree_20261019/scan_r02.py"
