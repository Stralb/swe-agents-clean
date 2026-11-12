#!/bin/bash
#SBATCH --job-name=agentic-js
#SBATCH --output=logs/agentic-js-%j.out
#SBATCH --error=logs/agentic-js-%j.err
#SBATCH --time=2-00:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --partition=bigbatch

set -euo pipefail

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$ROOT"
mkdir -p logs data data/cache/github_agentic_js

source .venv/bin/activate
set -a
source .env.cluster
set +a

RUN_STAMP="${AGENTIC_RUN_STAMP:-$(date +%Y%m%d_%H%M%S)}"
export CONFIG="$ROOT/config.agentic_js.yml"
export DB_PATH="${AGENTIC_DB_PATH:-$ROOT/data/miner.agentic-js.${RUN_STAMP}.db}"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

printf "%s\n" "$DB_PATH" > "$ROOT/.current_agentic_js_db"
echo "CONFIG=$CONFIG"
echo "DB_PATH=$DB_PATH"

echo "Initializing fresh SQLite database..."
python scripts/init_fresh_db.py

python - <<'PYCOLLECT'
from src.pipeline.collect_pipeline import collect
from src.settings import load_settings

collect(load_settings())
PYCOLLECT

python - <<'PYREPORT'
import os
import sqlite3

db_path = os.environ["DB_PATH"]
con = sqlite3.connect(db_path)

for table in (
    "repos",
    "pull_requests",
    "issues",
    "cases",
    "ai_markers",
    "excluded_cases",
    "retrieval_queries",
):
    count = con.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]
    print(f"{table}: {count}")

print("\nCases by marker:")
for row in con.execute(
    """
    SELECT marker_text, marker_location, COUNT(DISTINCT pr_id)
    FROM ai_markers
    GROUP BY marker_text, marker_location
    ORDER BY COUNT(DISTINCT pr_id) DESC
    """
):
    print(row)

con.close()
PYREPORT
