#!/bin/bash
#SBATCH --job-name=telegram_plugin_eval
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:45:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
base="$HOME/research_artifacts/mcp_uploads/jobs/two_provider_atomic_20261020_v1"
python3 "$base/init.py" 08152
python3 "$base/modify.py" 08152
python3 "$base/scan_wrapper.py" 08152
