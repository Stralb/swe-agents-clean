#!/bin/bash
#SBATCH --job-name=voice_plugin_codeql
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
dir="$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v3"
python3 "$dir/init.py" 08152
python3 "$dir/modify.py" 08152
python3 "$dir/scan.py" 08152
