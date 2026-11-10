#!/bin/bash
#SBATCH --job-name=AG03581fix
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/03581_retry_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/03581_retry_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/evaluate_retry_03581_v2.py 03581
