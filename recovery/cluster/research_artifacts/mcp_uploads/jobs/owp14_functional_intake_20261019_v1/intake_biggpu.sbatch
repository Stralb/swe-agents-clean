#!/bin/bash
#SBATCH --job-name=OWP14_intake
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=02:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_functional_intake_20261019_v1/intake.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_functional_intake_20261019_v1/intake.py"
