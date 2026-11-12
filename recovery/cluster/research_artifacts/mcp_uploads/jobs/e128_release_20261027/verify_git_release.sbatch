#!/bin/bash
#SBATCH --job-name=e128gitverify
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:07:00
set -euo pipefail
umask 077
cd /tmp
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/e128_release_20261027/verify_git_release.py
echo E128_GITHUB_RELEASE_VERIFICATION_DONE
