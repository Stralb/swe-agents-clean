#!/bin/bash
#SBATCH --job-name=arno_rc5_release
#SBATCH --partition=stampede
#SBATCH --time=00:20:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_release_rc5_oct31/builder.py
