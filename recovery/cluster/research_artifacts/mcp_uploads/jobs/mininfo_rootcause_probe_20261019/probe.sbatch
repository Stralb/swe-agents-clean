#!/bin/bash
#SBATCH --job-name=owp_rootprobe
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:03:00
set -euo pipefail
python3 "$HOME/research_artifacts/mcp_uploads/jobs/mininfo_rootcause_probe_20261019/probe.py"
