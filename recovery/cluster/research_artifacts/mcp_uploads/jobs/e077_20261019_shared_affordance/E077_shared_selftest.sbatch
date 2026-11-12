#!/bin/bash
#SBATCH --job-name=E077_shared_unit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e077_20261019_shared_affordance/E077_shared_affordance_v0.py
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' ede064bdb72fb632d90d6aec537b7a5f62d74521351cb859453d3ea558bb92c6 "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
echo E077_SHARED_UNIT_OK