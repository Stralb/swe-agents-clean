#!/bin/bash
#SBATCH --job-name=OWP14_packets
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp14_20261018_v1/freeze14.py"
