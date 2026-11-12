#!/bin/bash
#SBATCH --job-name=arno_peerreview_v5
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
cd "$HOME/research_artifacts/mcp_uploads/jobs/arno_peer_review_recovery_20261101"
python3 -B build_review_release_v5.py
