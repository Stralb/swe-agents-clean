#!/bin/bash
#SBATCH --job-name=e128inspect
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:05:00
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/inspect.py
