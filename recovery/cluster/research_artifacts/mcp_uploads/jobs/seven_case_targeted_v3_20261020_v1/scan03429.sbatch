#!/bin/bash
#SBATCH --job-name=case03429_fixture
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
export NODE_PATH="$(npm root -g)"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_case_targeted_v3_20261020_v1/fix_scan.py" 03429
