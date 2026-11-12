#!/bin/bash
#SBATCH --job-name=E107_contrastive_units
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:06:00
set -euo pipefail
umask 077
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
D=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e107_20261020_multi_family_mechanism
printf '%s  %s\n' 6d6ae06baa96d1ef7fcf0fdac725307af63a5cc1430003ddcde9d3dae8cf94d0 "$D/E107_contrastive_agent_v0.py" | sha256sum -c -
printf '%s  %s\n' f0070a5336a96771a54500477552c2e0461b8be100905b0d1a1188c8999c9252 "$D/E107_multifamily_runner_v0.py" | sha256sum -c -
"$PY" -B "$D/E107_multifamily_runner_v0.py" --self-test
echo E107_ALL_TESTS_PASSED