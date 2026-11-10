#!/bin/bash
#SBATCH --job-name=arno_pack_sources
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/pack08152.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_replication_08152_12344_20261030_r1/pack12344.py
