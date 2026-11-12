#!/bin/bash
#SBATCH --job-name=arno_SIGG_pack
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_sigg_r02_r08_v6_20261030_r1/package.py
