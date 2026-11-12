#!/bin/bash
#SBATCH --job-name=arno_claim_delta
#SBATCH --partition=batch
#SBATCH --dependency=afterok:77953
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_claim_delta_20261029/apply_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_claim_delta_20261029/apply_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_claim_delta_20261029/audit.py --apply
