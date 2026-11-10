#!/bin/bash
#SBATCH --job-name=mininfo_3x4
#SBATCH --partition=batch
#SBATCH --cpus-per-task=3
#SBATCH --mem=16G
#SBATCH --time=00:50:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/mininfo_3x4_20261019_run01/scan12.py"
