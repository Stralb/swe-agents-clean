#!/bin/bash
#SBATCH --job-name=arno_v2_evidence
#SBATCH --partition=batch
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=arno_v2_evidence_%j.log
set -euo pipefail
cd "$SLURM_SUBMIT_DIR"
python3 wits_integrate_v2.py --execute
