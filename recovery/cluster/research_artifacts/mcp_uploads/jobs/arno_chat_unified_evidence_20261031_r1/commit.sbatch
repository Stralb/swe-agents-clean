#!/bin/bash
#SBATCH --job-name=ARNOchatDBIngest
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=12G
#SBATCH --time=00:40:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/commit_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/commit_%j.err
set -euo pipefail
umask 077
python3 -m py_compile /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/ingest_prepare.py /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/ingest_prepare_v2.py /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/ingest_commit.py
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/ingest_commit.py
