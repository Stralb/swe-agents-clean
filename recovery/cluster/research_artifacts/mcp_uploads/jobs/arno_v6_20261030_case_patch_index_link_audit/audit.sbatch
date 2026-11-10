#!/bin/bash
#SBATCH --job-name=arno_v6_case_patch_link
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3G
#SBATCH --time=00:25:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case_patch_index_link_audit/audit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case_patch_index_link_audit/audit_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case_patch_index_link_audit/audit.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_v6_20261030_case_patch_index_link_audit/audit.py
