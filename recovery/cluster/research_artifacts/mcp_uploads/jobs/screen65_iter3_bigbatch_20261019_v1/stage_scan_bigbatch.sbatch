#!/bin/bash
#SBATCH --job-name=screen65_it3_cpu
#SBATCH --partition=bigbatch
#SBATCH --cpus-per-task=9
#SBATCH --mem=64G
#SBATCH --time=2-00:00:00
set -euo pipefail
export PATH="$HOME/tools/codeql:$HOME/tools/node/bin:/usr/bin:/bin"
python3 -m py_compile "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/stage.py" "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/scan65.py" "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/driver65.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/stage.py"
python3 "$HOME/research_artifacts/mcp_uploads/jobs/screen65_iter3_bigbatch_20261019_v1/driver65.py"
