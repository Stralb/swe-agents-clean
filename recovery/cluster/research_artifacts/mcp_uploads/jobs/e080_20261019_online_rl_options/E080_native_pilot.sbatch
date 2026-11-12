#!/bin/bash
#SBATCH --job-name=E080_native_pilot
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=6G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e080_20261019_online_rl_options/E080_native_option_prior_v0.py
printf '%s  %s\n' 60c64687a4eed82dd3c0ed776241c65c43c2f945988e76ecb96a05bd0f40e7fd "$SRC" | sha256sum -c -
OUT=/home-mscluster/astrauss/e080_course_development/E080_native_seed28901_${SLURM_JOB_ID}
"$PY" -B "$SRC" --seed 28901 --budget 160 --out "$OUT"
echo E080_NATIVE_PILOT_DONE