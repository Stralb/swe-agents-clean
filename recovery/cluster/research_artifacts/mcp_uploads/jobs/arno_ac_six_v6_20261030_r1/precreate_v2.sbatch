#!/bin/bash
#SBATCH --job-name=arnoACmkdir
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:05:00
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac_six_v6_20261030_r1/precreate_v2.py
