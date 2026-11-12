#!/bin/bash
#SBATCH --job-name=arno_v6_delta_snapshot
#SBATCH --partition=batch
#SBATCH --dependency=afterok:78107
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:40:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261029_incremental_provenance_delta/run_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261029_incremental_provenance_delta/run_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261029_incremental_provenance_delta/backup.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261029_incremental_provenance_delta/backup.py
