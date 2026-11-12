#!/bin/bash
#SBATCH --job-name=arnoSCGGpack
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_scgg_03581_v6_20261030_r1/package_verified.py
