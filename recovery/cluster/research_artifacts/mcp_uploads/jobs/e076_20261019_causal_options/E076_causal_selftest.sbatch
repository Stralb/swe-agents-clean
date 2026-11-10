#!/bin/bash
#SBATCH --job-name=E076_causal_unit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
umask 077
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e076_20261019_causal_options/E076_causal_options_v0.py
printf '%s  %s\n' 0d59d9f4cba64d1f4f68576691703d034ceebcc80269bd4dcb051109473881f1 "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
echo E076_UNIT_OK