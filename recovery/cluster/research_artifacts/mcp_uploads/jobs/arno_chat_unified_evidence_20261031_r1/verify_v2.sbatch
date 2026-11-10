#!/bin/bash
#SBATCH --job-name=ARNOchatVerify2
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/verifyv2_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/verifyv2_%j.err
set -euo pipefail
umask 077
python3 -u /home-mscluster/astrauss/research_artifacts/mcp_uploads/jobs/arno_chat_unified_evidence_20261031_r1/ingest_prepare_v2.py
