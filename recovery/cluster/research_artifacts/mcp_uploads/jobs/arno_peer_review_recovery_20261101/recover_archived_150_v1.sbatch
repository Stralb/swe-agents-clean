#!/bin/bash
#SBATCH --job-name=arno_archive_recovery
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_peer_review_recovery_20261101"
python3 -B recover_archived_150_v1.py
