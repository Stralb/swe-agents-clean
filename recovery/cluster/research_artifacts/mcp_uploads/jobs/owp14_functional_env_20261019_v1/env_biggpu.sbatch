#!/bin/bash
#SBATCH --job-name=OWP14_toolchain
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_functional_env_20261019_v1/env.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_functional_env_20261019_v1/env.py"
