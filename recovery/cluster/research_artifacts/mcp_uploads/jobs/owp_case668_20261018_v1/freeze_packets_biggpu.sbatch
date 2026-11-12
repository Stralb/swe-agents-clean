#!/bin/bash
#SBATCH --job-name=OWP668_packets
#SBATCH --partition=biggpu
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/owp_case668_20261018_v1/freeze_packets.py"
