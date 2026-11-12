#!/bin/bash
#SBATCH --job-name=OWP14_toolpaths
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_toolpaths_20261019_v1/toolpaths.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_toolpaths_20261019_v1/toolpaths.py"
