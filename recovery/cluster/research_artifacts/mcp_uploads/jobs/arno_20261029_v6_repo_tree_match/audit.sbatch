#!/bin/bash
#SBATCH --job-name=arno_v6_repo_equality
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=01:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/audit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/audit_%j.err
set -euo pipefail
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/audit.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_20261029_v6_repo_tree_match/audit.py
