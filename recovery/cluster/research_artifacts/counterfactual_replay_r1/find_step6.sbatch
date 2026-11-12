#!/bin/bash
#SBATCH --job-name=cf_find_s6
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/logs/%x_%j.err

set -euo pipefail

OUT="$HOME/research_artifacts/counterfactual_replay_r1"
RESULT="$OUT/STEP6_LOCATIONS.txt"

: > "$RESULT"

echo "============================================================" | tee -a "$RESULT"
echo "TARGETED STEP-6 ARTIFACT SEARCH" | tee -a "$RESULT"
echo "HOST=$(hostname)" | tee -a "$RESULT"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$RESULT"
echo "============================================================" | tee -a "$RESULT"

echo | tee -a "$RESULT"
echo "=== EXACT COMMON LOCATIONS ===" | tee -a "$RESULT"

for P in \
  "$HOME/DECISION_LEVEL_CONTROLS_STEP6_v1.0/STEP6_UNBLINDED_PAIRS_51.csv" \
  "$HOME/research_artifacts/DECISION_LEVEL_CONTROLS_STEP6_v1.0/STEP6_UNBLINDED_PAIRS_51.csv" \
  "$HOME/DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz" \
  "$HOME/research_artifacts/DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz"
do
    if [ -e "$P" ]; then
        ls -lh "$P" | tee -a "$RESULT"
    fi
done

echo | tee -a "$RESULT"
echo "=== RESEARCH_ARTIFACTS SEARCH ===" | tee -a "$RESULT"

if [ -d "$HOME/research_artifacts" ]; then
    find "$HOME/research_artifacts" \
      -maxdepth 6 \
      -type f \
      \( \
        -name 'STEP6_UNBLINDED_PAIRS_51.csv' \
        -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz' \
        -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.zip' \
        -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.xlsx' \
        -o -name 'STEP4_PRIMARY_MATCHES_31.csv' \
        -o -name 'STEP4_DECISION_MATCHES_51.csv' \
      \) \
      -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' \
      2>/dev/null | sort -r | tee -a "$RESULT"
fi

echo | tee -a "$RESULT"
echo "=== SHALLOW HOME SEARCH ===" | tee -a "$RESULT"

find "$HOME" \
  -maxdepth 3 \
  -type f \
  \( \
    -name 'STEP6_UNBLINDED_PAIRS_51.csv' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.zip' \
    -o -name 'DECISION_LEVEL_CONTROLS_STEP6_v1.0.xlsx' \
    -o -name 'STEP4_PRIMARY_MATCHES_31.csv' \
    -o -name 'STEP4_DECISION_MATCHES_51.csv' \
  \) \
  -printf '%TY-%Tm-%Td %TH:%TM:%TS %s %p\n' \
  2>/dev/null | sort -r | tee -a "$RESULT"

echo | tee -a "$RESULT"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$RESULT"
