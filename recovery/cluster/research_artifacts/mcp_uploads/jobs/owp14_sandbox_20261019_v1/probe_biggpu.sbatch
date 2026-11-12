#!/bin/bash
#SBATCH --job-name=OWP14_sandbox
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_sandbox_20261019_v1/probe.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_sandbox_20261019_v1/probe.py"
