#!/bin/bash
#SBATCH --job-name=arno22223preflight
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_functional_20261030_r1/preflight_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_functional_20261030_r1/preflight_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_case22223_functional_20261030_r1/preflight.py
