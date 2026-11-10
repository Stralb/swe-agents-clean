#!/bin/bash
#SBATCH --job-name=SPSCGGpack
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_spscgg_12344_v6_20261030_r1/package_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_spscgg_12344_v6_20261030_r1/package_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_spscgg_12344_v6_20261030_r1/package_evidence.py
