#!/bin/bash
#SBATCH --job-name=AGlast3Package
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:25:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/pack_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/pack_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_last3_v6_20261031_r1/package.py
