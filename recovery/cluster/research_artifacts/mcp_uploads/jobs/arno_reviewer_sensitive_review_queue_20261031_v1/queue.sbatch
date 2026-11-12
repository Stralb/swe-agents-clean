#!/bin/bash
#SBATCH --job-name=arno_manual_queue
#SBATCH --partition=stampede
#SBATCH --time=00:08:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_reviewer_sensitive_review_queue_20261031_v1/queue.py
