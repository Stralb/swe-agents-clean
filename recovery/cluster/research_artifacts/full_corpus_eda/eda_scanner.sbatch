#!/bin/bash
#SBATCH --job-name=eda-scanner
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
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
echo "MODE=scanner"

"$PY" "$ROOT/eda_parallel.py" scanner "$DB" "$RUN_DIR"

RC=$?

echo "RETURN_CODE=$RC"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test "$RC" -eq 0
