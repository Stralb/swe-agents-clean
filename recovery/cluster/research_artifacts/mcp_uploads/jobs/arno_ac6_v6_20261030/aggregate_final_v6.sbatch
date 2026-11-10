#!/bin/bash
#SBATCH --job-name=arno_ac6_final_v6
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=10G
#SBATCH --time=00:45:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/final_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/final_%j.err
set -euo pipefail
umask 077
python3 -m py_compile "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/aggregate_v6d.py" "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/package_v6d.py"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/aggregate_v6d.py"
python3 -u "/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_ac6_v6_20261030/package_v6d.py"
