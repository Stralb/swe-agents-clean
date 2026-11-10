#!/bin/bash
#SBATCH --job-name=cf_replay_s1
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

echo "============================================================"
echo "COUNTERFACTUAL REPLAY STEP 1"
echo "HOST=$(hostname)"
echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "============================================================"

python3 "$OUT/build_replay_candidates.py"

echo
echo "=== OUTPUT FILES ==="
ls -lh \
  "$OUT/replay_candidates_D1_22.csv" \
  "$OUT/STEP1_QC.txt"

echo
echo "=== QC ==="
cat "$OUT/STEP1_QC.txt"

echo
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
