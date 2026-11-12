#!/bin/bash
#SBATCH --job-name=OWPBlindPackets
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:45:00
set -euo pipefail
export PYTHONUNBUFFERED=1
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_pilot_packets_20261018_v1/prepare_packets_v2.py"
