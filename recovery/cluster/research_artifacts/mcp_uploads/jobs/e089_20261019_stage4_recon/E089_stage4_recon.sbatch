#!/bin/bash
#SBATCH --job-name=E089_stage4_probe
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:09:00
set -euo pipefail
umask 077
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
SRC=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e089_20261019_stage4_recon/E089_stage4_recon.py
printf '%s  %s\n' fcb95add9fa4317852cf82fbf9c3015f1ec9bd61a6072230557c03091d6f48a6 "$SRC" | sha256sum -c -
/home-mscluster/astrauss/arc_rl_mechanics_killtest/.venv/bin/python -B "$SRC"
echo E089_NEXT_STAGE_VISUAL_PROBE_DONE