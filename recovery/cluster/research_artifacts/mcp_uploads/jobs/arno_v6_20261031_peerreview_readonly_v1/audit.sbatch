#!/bin/bash
#SBATCH --job-name=arno_pr_audit
#SBATCH --partition=stampede
#SBATCH --time=00:15:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261031_peerreview_readonly_v1/audit-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261031_peerreview_readonly_v1/audit-%j.err
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261031_peerreview_readonly_v1/audit.py
