#!/bin/bash
#SBATCH --job-name=arno_owp40_preflight
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/preflight_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/preflight_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/normalize.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_owp40_fixed_v3/normalize.py
