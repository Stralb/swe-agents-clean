#!/bin/bash
#SBATCH --job-name=arno_ac6_evidence_v6e
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=10G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/final_e_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/final_e_%j.err
set -euo pipefail
umask 077
python3 -m py_compile "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/aggregate_v6e.py" "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/package_v6e.py"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/aggregate_v6e.py"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/package_v6e.py"
