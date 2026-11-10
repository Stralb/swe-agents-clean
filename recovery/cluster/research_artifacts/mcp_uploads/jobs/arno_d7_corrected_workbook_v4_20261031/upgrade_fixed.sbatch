#!/bin/bash
#SBATCH --job-name=arno_correct_d7_v4fix
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_d7_corrected_workbook_v4_20261031/upgrade_fixed.py
