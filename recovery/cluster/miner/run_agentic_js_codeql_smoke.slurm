#!/bin/bash
#SBATCH --job-name=agentic-codeql
#SBATCH --output=logs/agentic-codeql-%j.out
#SBATCH --error=logs/agentic-codeql-%j.err
#SBATCH --partition=bigbatch
#SBATCH --time=06:00:00
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
export DB_PATH="$(cat "$ROOT/.current_agentic_js_eval_db")"
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

unset MAX_CASES MAX_PRS MAX_REPOS MAX_SECONDS

command -v codeql
codeql version

echo "CONFIG=$CONFIG"
echo "DB_PATH=$DB_PATH"

python - <<'PY'
import os
import sqlite3

con = sqlite3.connect(os.environ["DB_PATH"])

print("Cases:", con.execute(
    "SELECT COUNT(*) FROM cases"
).fetchone()[0])

print("Existing CodeQL aggregate runs:", con.execute("""
    SELECT COUNT(*)
    FROM scanner_runs
    WHERE scanner = 'codeql'
""").fetchone()[0])

print("Pending CodeQL jobs:", con.execute("""
    SELECT COUNT(*)
    FROM scanner_jobs
    WHERE job_type = 'codeql'
      AND status = 'pending'
""").fetchone()[0])

con.close()
PY

python - <<'PY'
from src.pipeline.scan_pipeline import scan
from src.settings import load_settings

settings = load_settings()

scanners = settings.config.setdefault("scanners", {})

# Existing cheap scanners already completed.
scanners["codeql"] = True
scanners["semgrep"] = False
scanners["gitleaks"] = True
scanners["osv"] = True
scanners["dependency_downgrade"] = True

scanners["codeql_language"] = "auto"
scanners["codeql_trigger"] = "all_codeql"
scanners["codeql_timeout_seconds"] = 1800

settings.config.setdefault("scan", {})["codeql_max_per_run"] = 3
settings.config.setdefault("cache", {})["force_rescan"] = False

print("Starting CodeQL smoke test")
print("Maximum aggregate CodeQL cases this run: 3")

scan(settings)
PY

python - <<'PY'
import os
import sqlite3

con = sqlite3.connect(os.environ["DB_PATH"])

print("\n===== CODEQL RESULT =====")

print("Cases with aggregate CodeQL records:", con.execute("""
    SELECT COUNT(DISTINCT case_id)
    FROM scanner_runs
    WHERE scanner = 'codeql'
""").fetchone()[0])

print("All CodeQL-family runs:", con.execute("""
    SELECT COUNT(*)
    FROM scanner_runs
    WHERE scanner LIKE 'codeql%'
""").fetchone()[0])

print("CodeQL findings:", con.execute("""
    SELECT COUNT(*)
    FROM scanner_findings
    WHERE scanner = 'codeql'
""").fetchone()[0])

print("\nRuns by scanner/status:")
for row in con.execute("""
    SELECT scanner, status, COUNT(*)
    FROM scanner_runs
    WHERE scanner LIKE 'codeql%'
    GROUP BY scanner, status
    ORDER BY scanner, status
"""):
    print(row)

print("\nAggregate CodeQL case results:")
for row in con.execute("""
    SELECT
        sr.case_id,
        r.full_name,
        p.number,
        sr.status,
        sr.stdout,
        substr(sr.stderr, 1, 400)
    FROM scanner_runs sr
    JOIN cases c ON c.id = sr.case_id
    JOIN repos r ON r.id = c.repo_id
    JOIN pull_requests p ON p.id = c.pr_id
    WHERE sr.scanner = 'codeql'
    ORDER BY sr.id
"""):
    print(row)

con.close()
PY
