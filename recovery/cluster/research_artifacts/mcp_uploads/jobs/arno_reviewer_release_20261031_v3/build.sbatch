#!/bin/bash
#SBATCH --job-name=arno_reviewer_candidate
#SBATCH --partition=bigbatch
#SBATCH --time=00:40:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_reviewer_release_20261031_v3/job-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_reviewer_release_20261031_v3/job-%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_reviewer_release_20261031_v3/build.py
