#!/bin/bash
#SBATCH --job-name=arno_archive_apply_v3
#SBATCH --partition=batch
#SBATCH --dependency=afterok:77957
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=3
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_archive_source_registry_v3/apply_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_archive_source_registry_v3/apply_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_archive_source_registry_v3/index.py --apply
