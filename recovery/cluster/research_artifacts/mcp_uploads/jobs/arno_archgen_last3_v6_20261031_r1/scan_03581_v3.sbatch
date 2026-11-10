#!/bin/bash
#SBATCH --job-name=AG3581V3
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/03581v3_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/03581v3_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/evaluate_03581_v3.py 03581
