#!/bin/bash
#SBATCH --job-name=OWP14_syntax2
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=18G
#SBATCH --time=02:00:00
set -euo pipefail
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_syntax_20261019_v2/syntax.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_syntax_20261019_v2/syntax.py"
