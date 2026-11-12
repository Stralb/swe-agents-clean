#!/bin/bash
#SBATCH --job-name=E093_from_reset_full
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=5G
#SBATCH --time=00:20:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
DIR=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e093_20261020_online_hypothesis
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
printf '%s  %s\n' d27469802f40beb019e62c7412f51bc80f668a51305a664eff0bfaad750f8786 "$DIR/E093_native_runner_v0.py" | sha256sum -c -
printf '%s  %s\n' 4c52eb6cb3c5fb4d4aced65bfe525722e0d7aa813dd9f028ccd7bc0c06cde018 "$DIR/E093_online_core_v0.py" | sha256sum -c -
OUT="/home-mscluster/astrauss/e093_from_reset_research/E093_seed28901_full_${SLURM_JOB_ID}"
"$PY" -B "$DIR/E093_native_runner_v0.py" --mode full --seed 28901 --budget 160 --out "$OUT"
echo "E093_PILOT_SUCCESS $OUT/E093_REPORT.json"