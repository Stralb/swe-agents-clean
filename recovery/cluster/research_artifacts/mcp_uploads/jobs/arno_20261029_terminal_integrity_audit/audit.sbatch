#!/bin/bash
#SBATCH --job-name=arno_master_audit
#SBATCH --dependency=afterok:77765
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/final_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/final_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_terminal_integrity_audit/audit.py
