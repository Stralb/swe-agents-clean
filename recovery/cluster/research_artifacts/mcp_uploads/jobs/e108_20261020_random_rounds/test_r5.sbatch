#!/bin/bash
#SBATCH --job-name=E108_motion_unit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
export OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
printf '%s  %s\n' 421dc987ac94fcaa716e24aaeda8d34d83afd7088345fd18dc3e70105177495d "$D/policy_r5_fast.py" | sha256sum -c -
printf '%s  %s\n' 3222cc66137b05fb3dadb930994c01da36a16854adffc3e4242d8c60d640e2f9 "$D/policy_r5.py" | sha256sum -c -
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python -B "$D/policy_r5_fast.py"
