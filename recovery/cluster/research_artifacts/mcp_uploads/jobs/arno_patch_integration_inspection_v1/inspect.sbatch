#!/bin/bash
#SBATCH --job-name=arno_patch_stage_discovery
#SBATCH --partition=stampede
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_patch_integration_inspection_v1/inspect.py
