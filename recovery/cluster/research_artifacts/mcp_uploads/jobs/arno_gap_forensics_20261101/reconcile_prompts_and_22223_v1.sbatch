#!/bin/bash
#SBATCH --job-name=arno_prompt_22223_proof
#SBATCH --partition=bigbatch
#SBATCH --time=00:40:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_gap_forensics_20261101"
python3 -B reconcile_prompts_and_22223_v1.py
