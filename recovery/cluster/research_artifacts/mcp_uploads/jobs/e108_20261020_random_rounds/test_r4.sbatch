#!/bin/bash
#SBATCH --job-name=E108_Dyna_unit
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:05:00
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e108_20261020_random_rounds
printf '%s  %s\n' fb1b8482deb5b56b58bf6f674fccf42731ce2969a7db5a4398e8f271599204aa "$D/policy_r4.py" | sha256sum -c -
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python -B "$D/policy_r4.py"
