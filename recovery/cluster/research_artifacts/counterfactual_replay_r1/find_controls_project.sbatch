#!/bin/bash
#SBATCH --job-name=cf_find_ctrl
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

PROJECT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
OUT="$HOME/research_artifacts/counterfactual_replay_r1"
RESULT="$OUT/PROJECT_CONTROL_ARTIFACTS.txt"

: > "$RESULT"

echo "============================================================" | tee -a "$RESULT"
echo "BOUNDED DECISION-CONTROL ARTIFACT SEARCH" | tee -a "$RESULT"
echo "HOST=$(hostname)" | tee -a "$RESULT"
echo "PROJECT=$PROJECT" | tee -a "$RESULT"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$RESULT"
echo "============================================================" | tee -a "$RESULT"

if [ ! -d "$PROJECT" ]; then
    echo "PROJECT_ROOT_MISSING" | tee -a "$RESULT"
    exit 2
fi

find "$PROJECT" \
  -maxdepth 10 \
  -type f \
  \( \
    -name 'STEP6_UNBLINDED_PAIRS_51.csv' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.zip' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.xlsx' \
    -o -name 'STEP4_DECISION_MATCHES_51.csv' \
    -o -name 'STEP4_PRIMARY_MATCHES_31.csv' \
    -o -name 'STEP4_BLINDED_DECISION_PACKETS_102.csv' \
    -o -iname '*decision*control*step4*' \
    -o -iname '*decision*control*step5*' \
    -o -iname '*decision*control*step6*' \
  \) \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS\t%s\t%p\n' \
  2>/dev/null |
  sort -r |
  tee -a "$RESULT"

echo | tee -a "$RESULT"
echo "============================================================" | tee -a "$RESULT"
echo "DIRECTORY-NAME CHECK" | tee -a "$RESULT"
echo "============================================================" | tee -a "$RESULT"

find "$PROJECT" \
  -maxdepth 8 \
  -type d \
  \( \
    -iname '*decision*control*' \
    -o -iname '*step4*' \
    -o -iname '*step5*' \
    -o -iname '*step6*' \
  \) \
  -print \
  2>/dev/null |
  sort |
  tee -a "$RESULT"

echo | tee -a "$RESULT"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$RESULT"
