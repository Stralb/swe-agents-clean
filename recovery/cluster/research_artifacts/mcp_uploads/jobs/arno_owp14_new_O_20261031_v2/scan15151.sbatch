#!/bin/bash
#SBATCH --job-name=owp_new_o_15151
#SBATCH --partition=bigbatch
#SBATCH --time=03:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_v2/run-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_v2/run-%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_owp14_new_O_20261031_v2/scan15151.py
