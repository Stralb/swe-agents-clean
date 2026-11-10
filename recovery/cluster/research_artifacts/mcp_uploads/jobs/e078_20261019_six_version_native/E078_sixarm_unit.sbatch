#!/bin/bash
#SBATCH --job-name=E078_sixarm_unit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e078_20261019_six_version_native/E078_six_version_native_v0.py
printf '%s  %s\n' dcb59636a9ffd7319ebd0a2ec692cd20200532845f00d6be1caba6927c6d0fd3 "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
echo E078_SIX_VERSION_SELFTEST_COMPLETE