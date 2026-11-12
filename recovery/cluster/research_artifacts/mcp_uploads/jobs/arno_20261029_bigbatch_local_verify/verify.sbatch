#!/bin/bash
#SBATCH --job-name=arno_bigbatch_verify
#SBATCH --partition=bigbatch
#SBATCH --nodelist=mscluster63
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=1-00:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_bigbatch_local_verify/check_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_bigbatch_local_verify/check_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_bigbatch_local_verify/verify.py
