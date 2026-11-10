#!/bin/bash
#SBATCH --job-name=E078_sixarm_native
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e078_20261019_six_version_native/E078_six_version_native_v0.py
printf '%s  %s\n' dcb59636a9ffd7319ebd0a2ec692cd20200532845f00d6be1caba6927c6d0fd3 "$SRC" | sha256sum -c -
OUT=/home-mscluster/astrauss/e078_course_recovery/E078_native_vc33_160_seed28901_${SLURM_JOB_ID}
"$PY" -B "$SRC" --seed 28901 --budget 160 --full-controls --out "$OUT"
echo "E078_NATIVE_SIXARM_COMPLETE $OUT/E078_REPORT.json"