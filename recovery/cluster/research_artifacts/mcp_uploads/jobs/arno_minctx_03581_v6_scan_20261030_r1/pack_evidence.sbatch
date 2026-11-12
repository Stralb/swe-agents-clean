#!/bin/bash
#SBATCH --job-name=arno03581pack
#SBATCH --partition=batch
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_minctx_03581_v6_scan_20261030_r1/pack_evidence.py
