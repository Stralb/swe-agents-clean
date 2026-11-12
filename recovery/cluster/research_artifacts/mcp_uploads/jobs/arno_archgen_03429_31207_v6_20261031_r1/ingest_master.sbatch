#!/bin/bash
#SBATCH --job-name=ARCHGEN_DB
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/db_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/db_%j.err
set -euo pipefail
umask 077
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/ingest_master.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_archgen_03429_31207_v6_20261031_r1/ingest_master.py
