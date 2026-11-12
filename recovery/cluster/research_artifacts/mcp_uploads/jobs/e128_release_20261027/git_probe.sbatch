#!/bin/bash
#SBATCH --job-name=e128gitprobe
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=1G
#SBATCH --time=00:04:00
set -euo pipefail
umask 077
cd /tmp
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/git_probe.py
