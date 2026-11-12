#!/bin/bash
#SBATCH --job-name=cf_ctx10
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

OUT="$HOME/research_artifacts/counterfactual_replay_r1"
PROJECT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"

echo "============================================================"
echo "COUNTERFACTUAL REPLAY STEP 3"
echo "FULL CONTEXT FOR 10 SHORTLISTED CASES"
echo "============================================================"
echo "HOST=$(hostname)"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "PARTITION=biggpu"
echo

python3 \
  "$OUT/extract_step3_context.py" \
  "$OUT" \
  "$PROJECT"

echo
echo "============================================================"
echo "FILES"
echo "============================================================"

ls -lh \
  "$OUT/STEP3_selected_cases.csv" \
  "$OUT/STEP3_selected_case_context_10.csv" \
  "$OUT/STEP3_CONTEXT_QC.txt" \
  "$OUT/STEP3_DB_DISCOVERY.txt"

echo
echo "============================================================"
echo "SHA256"
echo "============================================================"

sha256sum \
  "$OUT/STEP3_selected_case_context_10.csv" \
  "$OUT/STEP3_CONTEXT_QC.txt"

echo
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
