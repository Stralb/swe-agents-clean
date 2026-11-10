#!/bin/bash
#SBATCH --job-name=recover24_issues
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recover24_20261017_v1/slurm-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recover24_20261017_v1/slurm-%j.err
#SBATCH --chdir=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recover24_20261017_v1

set -euo pipefail
SCRIPT="/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/recover24_20261017_v1/recover_original_issues.py"
printf '%s  %s\n' '9b5f76118a8f91a8804ff8ec2d322066e08c7a72cbe1dc457a807af844cc90cd' "$SCRIPT" | sha256sum --check --status
python3 "$SCRIPT"
