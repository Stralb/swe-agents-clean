#!/bin/bash
#SBATCH --job-name=OWP14_subtests
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_targeted_behavior_20261019_v1/behavior.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_targeted_behavior_20261019_v1/behavior.py"
