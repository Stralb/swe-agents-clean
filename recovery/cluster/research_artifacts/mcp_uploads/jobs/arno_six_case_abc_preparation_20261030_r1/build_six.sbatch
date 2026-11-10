#!/bin/bash
#SBATCH --job-name=arno6_abcpackets
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=10G
#SBATCH --time=02:00:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/build_six_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/build_six_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_six_case_abc_preparation_20261030_r1/build_six.py
