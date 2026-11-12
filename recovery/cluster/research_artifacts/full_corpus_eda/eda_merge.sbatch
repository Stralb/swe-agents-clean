#!/bin/bash
#SBATCH --job-name=eda-merge
#SBATCH --partition=batch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/full_corpus_eda/logs/%x-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/full_corpus_eda/logs/%x-%j.err

ROOT="$HOME/research_artifacts/full_corpus_eda"
REPO="$HOME/new/malicious-issue-miner-rate-smart"
DB="$REPO/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
PY="$REPO/.venv/bin/python"

if [ ! -x "$PY" ]; then
    PY="python3"
fi

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "HOST=$(hostname)"
echo "MODE=merge"

"$PY" "$ROOT/eda_parallel.py" \
    merge \
    "$DB" \
    "$RUN_DIR" \
    "$ROOT/validated_positive_122.txt" \
    "$ROOT/excluded_16.txt"

RC=$?

echo "RETURN_CODE=$RC"

if [ "$RC" -eq 0 ]; then
    ln -sfn "$RUN_DIR" "$ROOT/LATEST" || true
    ln -sfn "${RUN_DIR}.zip" "$ROOT/LATEST.zip" || true
    sha256sum "${RUN_DIR}.zip" > "${RUN_DIR}.zip.sha256" || true
fi

echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test "$RC" -eq 0
