#!/bin/bash
#SBATCH --job-name=eda3809
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/full_corpus_eda/logs/%x-%j.out
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/full_corpus_eda/logs/%x-%j.err

REPO="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
DB="$REPO/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
ROOT="$HOME/research_artifacts/full_corpus_eda"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/eda3809_$STAMP"

PYTHON="$REPO/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    PYTHON="python3"
fi

mkdir -p "$OUT" || true

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "HOST=$(hostname)"
echo "DB=$DB"
echo "OUT=$OUT"
echo "PYTHON=$PYTHON"

"$PYTHON" "$ROOT/eda3809.py" "$DB" "$OUT"
RC=$?

echo "RETURN_CODE=$RC"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [ "$RC" -eq 0 ]; then
    ln -sfn "$OUT" "$ROOT/LATEST" || true
    ln -sfn "${OUT}.zip" "$ROOT/LATEST.zip" || true
    sha256sum "${OUT}.zip" > "${OUT}.zip.sha256" || true
fi

test "$RC" -eq 0
