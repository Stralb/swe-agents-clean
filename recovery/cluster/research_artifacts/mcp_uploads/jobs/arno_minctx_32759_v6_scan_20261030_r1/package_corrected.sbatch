#!/bin/bash
#SBATCH --job-name=arno32759evidence
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_minctx_32759_v6_scan_20261030_r1/package_corrected.py
