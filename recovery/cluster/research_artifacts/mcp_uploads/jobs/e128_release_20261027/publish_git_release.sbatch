#!/bin/bash
#SBATCH --job-name=e128publish
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:08:00
set -euo pipefail
umask 077
cd /tmp
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/publish_git_release.py
echo E128_GITHUB_FEATURE_PUSH_DONE
