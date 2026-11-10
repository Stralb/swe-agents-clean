#!/bin/bash
#SBATCH --job-name=E108_read_contract
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
P=/home-mscluster/astrauss/RL-ARC-AGI-3-Project
printf '=== ADAPTER ===\n'
sed -n '1,390p' "$P/src/adapter.py"
printf '=== TRACKER ===\n'
if [ -f "$P/src/budget.py" ]; then sed -n '1,240p' "$P/src/budget.py"; fi
printf '=== SCRIPTS IN THIS ROTATION (NO GAME FILES) ===\n'
find /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs -maxdepth 1 -type d -name 'e108*' -print
