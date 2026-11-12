#!/bin/bash
#SBATCH --job-name=E076_causal_unit_v1
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e076_20261019_causal_options_v1/E076_causal_options_v1.py
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' 8b0f0b4873e39d103fcb3754e04f82b42d4f279df3d586b3625ec797131166b4 "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
echo E076_V1_UNIT_PASSED