#!/bin/bash
#SBATCH --job-name=arno_archive_inventory
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_archive_audit_v1/%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_archive_audit_v1/%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261030_archive_audit_v1/audit.py
