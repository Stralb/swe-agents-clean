#!/bin/bash
#SBATCH --job-name=E080_option_unit
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:07:00
set -euo pipefail
export OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1
PY=/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e080_20261019_online_rl_options/E080_native_option_prior_v0.py
printf '%s  %s\n' 60c64687a4eed82dd3c0ed776241c65c43c2f945988e76ecb96a05bd0f40e7fd "$SRC" | sha256sum -c -
"$PY" -B "$SRC" --self-test
echo E080_UNITS_VERIFIED