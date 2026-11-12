#!/bin/bash
#SBATCH --job-name=arno_rc5_final_crc
#SBATCH --partition=stampede
#SBATCH --time=00:07:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_rc5_final_gate_20261031_v1/check.py
