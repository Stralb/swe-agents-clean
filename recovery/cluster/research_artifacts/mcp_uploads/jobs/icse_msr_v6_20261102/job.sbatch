#!/bin/bash
#SBATCH --job-name=arno_msr_deep
#SBATCH --partition=stampede
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=00:35:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/icse_msr_v6_20261102/job.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/icse_msr_v6_20261102/job.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/icse_msr_v6_20261102/analysis.py
