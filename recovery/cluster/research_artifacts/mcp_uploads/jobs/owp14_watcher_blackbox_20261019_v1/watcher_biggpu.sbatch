#!/bin/bash
#SBATCH --job-name=OWP14_watcher
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=00:30:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_watcher_blackbox_20261019_v1/watcher.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_watcher_blackbox_20261019_v1/watcher.py"
