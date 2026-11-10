#!/bin/bash
#SBATCH --job-name=arno6_verify_v6
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/verify_v6_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/verify_v6_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/verify_six_v6.py
