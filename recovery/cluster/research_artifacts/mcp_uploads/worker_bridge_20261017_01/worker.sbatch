#!/bin/bash
#SBATCH --job-name=research_bridge
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=worker-%j.out
#SBATCH --error=worker-%j.err
set -euo pipefail
# Administrator must ensure execution identity cannot write to historical datasets.
# Configure WORKER_BRIDGE_ROOT and WORKER_BRIDGE_SCRIPT for your isolated workspace.
: "${WORKER_BRIDGE_ROOT:?Set worker bridge root}"
: "${WORKER_BRIDGE_SCRIPT:?Set path to worker.py}"
exec python3 "$WORKER_BRIDGE_SCRIPT"
