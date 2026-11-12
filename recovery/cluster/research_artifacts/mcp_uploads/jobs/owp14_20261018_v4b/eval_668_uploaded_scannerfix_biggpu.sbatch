#!/bin/bash
#SBATCH --job-name=OWP668_eval_v4b
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:$HOME/.bun/bin:$PATH"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/owp14_20261018_v4b/eval_668_uploaded_scannerfix.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_20261018_v4b/eval_668_uploaded_scannerfix.py"
