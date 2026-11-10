#!/bin/bash
#SBATCH --job-name=e128build
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
ROOT=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027
PY=/home-mscluster/astrauss/arc26/.venv_cuda130/bin/python
"$PY" -m py_compile "$ROOT/e126_template.py" "$ROOT/build_release.py"
"$PY" "$ROOT/build_release.py"
echo E128_RELEASE_BUILD_SUCCESS
