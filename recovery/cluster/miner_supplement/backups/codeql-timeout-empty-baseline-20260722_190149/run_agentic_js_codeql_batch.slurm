#!/bin/bash
#SBATCH --job-name=codeql-batch
#SBATCH --output=logs/codeql-batch-%j.out
#SBATCH --error=logs/codeql-batch-%j.err
#SBATCH --partition=bigbatch
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G

set -euo pipefail

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$ROOT"

mkdir -p logs
source .venv/bin/activate

set -a
source .env.cluster
set +a

export CONFIG="$ROOT/config.agentic_js.yml"
export DB_PATH="$(tr -d '[:space:]' < "$ROOT/.current_agentic_js_eval_db")"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

unset MAX_CASES MAX_PRS MAX_REPOS MAX_SECONDS

echo "DB_PATH=$DB_PATH"
command -v codeql
codeql version

python - <<'PY'
import sqlite3

from src.pipeline.scan_pipeline import scan
from src.settings import load_settings

settings = load_settings()

scanners = settings.config.setdefault("scanners", {})

scanners["codeql"] = True
scanners["semgrep"] = False
scanners["gitleaks"] = True
scanners["osv"] = True
scanners["dependency_downgrade"] = True

scanners["codeql_language"] = "auto"
scanners["codeql_trigger"] = "all_codeql"
scanners["codeql_build_mode"] = "none"
scanners["codeql_timeout_seconds"] = 900

settings.config.setdefault("scan", {})[
    "codeql_max_per_run"
] = 10

settings.config.setdefault("cache", {})[
    "force_rescan"
] = False

con = sqlite3.connect(settings.db_path)

before = con.execute("""
    SELECT COUNT(DISTINCT case_id)
    FROM scanner_runs
    WHERE scanner = 'codeql'
""").fetchone()[0]

remaining = con.execute("""
    SELECT COUNT(*)
    FROM cases c
    WHERE NOT EXISTS (
        SELECT 1
        FROM scanner_runs sr
        WHERE sr.case_id = c.id
          AND sr.scanner = 'codeql'
    )
""").fetchone()[0]

con.close()

print("CodeQL cases before batch:", before, flush=True)
print("Cases remaining before batch:", remaining, flush=True)
print("Maximum cases this batch: 10", flush=True)

scan(settings)

con = sqlite3.connect(settings.db_path)

after = con.execute("""
    SELECT COUNT(DISTINCT case_id)
    FROM scanner_runs
    WHERE scanner = 'codeql'
""").fetchone()[0]

remaining_after = con.execute("""
    SELECT COUNT(*)
    FROM cases c
    WHERE NOT EXISTS (
        SELECT 1
        FROM scanner_runs sr
        WHERE sr.case_id = c.id
          AND sr.scanner = 'codeql'
    )
""").fetchone()[0]

findings = con.execute("""
    SELECT COUNT(*)
    FROM scanner_findings
    WHERE scanner = 'codeql'
""").fetchone()[0]

print("\n===== BATCH RESULT =====")
print("CodeQL cases after batch:", after)
print("New cases recorded:", after - before)
print("Cases remaining:", remaining_after)
print("CodeQL findings:", findings)

print("\nAggregate statuses:")
for row in con.execute("""
    SELECT status, COUNT(*)
    FROM scanner_runs
    WHERE scanner = 'codeql'
    GROUP BY status
    ORDER BY status
"""):
    print(row)

print("\nLatest aggregate runs:")
for row in con.execute("""
    SELECT
        sr.case_id,
        r.full_name,
        p.number,
        sr.status,
        sr.stdout,
        substr(sr.stderr, 1, 300)
    FROM scanner_runs sr
    JOIN cases c ON c.id = sr.case_id
    JOIN repos r ON r.id = c.repo_id
    JOIN pull_requests p ON p.id = c.pr_id
    WHERE sr.scanner = 'codeql'
    ORDER BY sr.id DESC
    LIMIT 12
"""):
    print(row)

con.close()
PY
