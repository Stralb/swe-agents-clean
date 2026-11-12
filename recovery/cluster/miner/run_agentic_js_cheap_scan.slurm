#!/bin/bash
#SBATCH --job-name=agentic-cheap
#SBATCH --output=logs/agentic-cheap-%j.out
#SBATCH --error=logs/agentic-cheap-%j.err
#SBATCH --partition=bigbatch
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$ROOT"

mkdir -p logs
source .venv/bin/activate

set -a
source .env.cluster
set +a

export CONFIG="$ROOT/config.agentic_js.yml"
export DB_PATH="$(cat "$ROOT/.current_agentic_js_eval_db")"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

# Prevent inherited limits from silently restricting the pass.
unset MAX_CASES MAX_PRS MAX_REPOS MAX_SECONDS

# Cheap/static analysis pass only.
export SCAN_CODEQL=false
export SCAN_SEMGREP=true
export SCAN_GITLEAKS=true
export SCAN_OSV=true
export SCAN_DEPENDENCY_DOWNGRADE=true
export FORCE_RESCAN=false

echo "CONFIG=$CONFIG"
echo "DB_PATH=$DB_PATH"

python - <<'PY'
import os
import sqlite3

db = os.environ["DB_PATH"]
con = sqlite3.connect(db)

print("Pre-scan cases:", con.execute(
    "SELECT COUNT(*) FROM cases"
).fetchone()[0])

print("Pre-scan runs:", con.execute(
    "SELECT COUNT(*) FROM scanner_runs"
).fetchone()[0])

print("Pre-scan findings:", con.execute(
    "SELECT COUNT(*) FROM scanner_findings"
).fetchone()[0])

con.close()
PY

python - <<'PY'
from src.pipeline.scan_pipeline import scan
from src.settings import load_settings

settings = load_settings()

print("Effective scanners:", settings.config["scanners"])
scan(settings)
PY

python - <<'PY'
import os
import sqlite3

db = os.environ["DB_PATH"]
con = sqlite3.connect(db)

print("\n===== POST-SCAN COUNTS =====")

for table in (
    "cases",
    "scanner_runs",
    "scanner_findings",
    "scanner_jobs",
):
    print(
        table,
        con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
    )

print("\nRuns by scanner and status:")
for row in con.execute("""
    SELECT scanner, status, COUNT(*)
    FROM scanner_runs
    GROUP BY scanner, status
    ORDER BY scanner, status
"""):
    print(row)

print("\nFindings:")
for row in con.execute("""
    SELECT scanner, finding_type, introduced, COUNT(*)
    FROM scanner_findings
    GROUP BY scanner, finding_type, introduced
    ORDER BY scanner, finding_type, introduced
"""):
    print(row)

print("\nCases never touched:")
for row in con.execute("""
    SELECT c.id
    FROM cases c
    WHERE NOT EXISTS (
        SELECT 1
        FROM scanner_runs sr
        WHERE sr.case_id = c.id
    )
    ORDER BY c.id
"""):
    print(row)

con.close()
PY
