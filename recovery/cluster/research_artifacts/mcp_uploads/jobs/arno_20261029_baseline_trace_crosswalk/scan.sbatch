#!/bin/bash
#SBATCH --job-name=arno_baseline_trace
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_baseline_trace_crosswalk/scan_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_baseline_trace_crosswalk/scan_%j.err
set -euo pipefail
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_baseline_trace_crosswalk/crosswalk.py
