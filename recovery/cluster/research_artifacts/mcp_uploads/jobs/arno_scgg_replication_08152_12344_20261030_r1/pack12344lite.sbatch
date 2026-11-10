#!/bin/bash
#SBATCH --job-name=arno_src_lite
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/pack12344lite.py
