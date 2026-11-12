#!/bin/bash
#SBATCH --job-name=seven_min_starter
#SBATCH --partition=batch
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:12:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/seven_minimum_starter_packets_20261020/build.py"
