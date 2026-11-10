#!/bin/bash
#SBATCH --job-name=telegram_typefix
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=2
#SBATCH --mem=5G
#SBATCH --time=00:12:00
set -euo pipefail
export PATH="$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v1/fix_bridge_type.py"
