#!/bin/bash
#SBATCH --job-name=arno_private_disclosure_scan
#SBATCH --partition=stampede
#SBATCH --time=00:25:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
set -euo pipefail
python3 /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_raw_disclosure_audit_20261031_v1/scan.py
