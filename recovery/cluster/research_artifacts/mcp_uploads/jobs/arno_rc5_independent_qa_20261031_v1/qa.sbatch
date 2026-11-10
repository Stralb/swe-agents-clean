#!/bin/bash
#SBATCH --job-name=arno_rc5_qa
#SBATCH --partition=stampede
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_rc5_independent_qa_20261031_v1/qa.py
