#!/bin/bash
#SBATCH --job-name=arnoACsummary
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --dependency=afterok:78855
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/aggregate.py
