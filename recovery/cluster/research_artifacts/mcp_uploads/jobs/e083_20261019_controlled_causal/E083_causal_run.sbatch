#!/bin/bash
#SBATCH --job-name=E083_controlled_probe
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:25:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e083_20261019_controlled_causal/E083_causal_contrast_v0.py
printf '%s  %s\n' 3b668d8355e607b0ee89198063d4e9dca336519f45c738344df827bba7d3906a "$SRC" | sha256sum -c -
OUT="/home-mscluster/astrauss/e083_single_game_causal/E083_vc33_${SLURM_JOB_ID}"
"$PY" -B "$SRC" --max-interventions 30 --out "$OUT"
echo E083_NATIVE_CAUSAL_PROBE_FINISHED