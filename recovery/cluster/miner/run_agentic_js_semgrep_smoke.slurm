#!/bin/bash
#SBATCH --job-name=agentic-semgrep
#SBATCH --output=logs/agentic-semgrep-%j.out
#SBATCH --error=logs/agentic-semgrep-%j.err
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G

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

echo "DB_PATH=$DB_PATH"
semgrep --version

python - <<'PY'
import os
import sqlite3

from src.db.database import Database
from src.pipeline.case_builder import update_case_tags_and_status
from src.scanners.scanner_runner import scan_case
from src.settings import load_settings

settings = load_settings()
db = Database(settings.db_path)

config = settings.config
scanners = config.setdefault("scanners", {})

scanners["semgrep"] = True
scanners["codeql"] = False
scanners["gitleaks"] = False
scanners["osv"] = False
scanners["dependency_downgrade"] = False
scanners["semgrep_config"] = "p/security-audit"
scanners["semgrep_timeout_seconds"] = 600

config.setdefault("cache", {})["force_rescan"] = False

cases = db.query("""
    SELECT
        c.id AS case_id,
        p.id AS pr_id,
        r.html_url AS repo_url,
        r.full_name AS repo_full_name,
        p.number AS pr_number,
        p.head_sha,
        p.base_sha
    FROM cases c
    JOIN repos r ON r.id = c.repo_id
    JOIN pull_requests p ON p.id = c.pr_id
    WHERE NOT EXISTS (
        SELECT 1
        FROM scanner_runs sr
        WHERE sr.case_id = c.id
          AND sr.scanner = 'semgrep'
    )
      AND EXISTS (
        SELECT 1
        FROM pr_files pf
        WHERE pf.pr_id = p.id
          AND (
              lower(pf.filename) LIKE '%.js'
              OR lower(pf.filename) LIKE '%.jsx'
              OR lower(pf.filename) LIKE '%.ts'
              OR lower(pf.filename) LIKE '%.tsx'
              OR lower(pf.filename) LIKE '%.mjs'
              OR lower(pf.filename) LIKE '%.cjs'
              OR lower(pf.filename) LIKE '%.vue'
          )
    )
    ORDER BY c.id
    LIMIT 3
""")

print("Selected smoke-test cases:", len(cases), flush=True)

for index, case in enumerate(cases, start=1):
    print(
        f"[{index}/{len(cases)}] "
        f"case={case['case_id']} "
        f"repo={case['repo_full_name']} "
        f"pr={case['pr_number']}",
        flush=True,
    )

    scan_case(db, case, config)

    run = db.one("""
        SELECT scanner, status, stdout, stderr
        FROM scanner_runs
        WHERE case_id=?
          AND scanner='semgrep'
        ORDER BY id DESC
        LIMIT 1
    """, (case["case_id"],))

    print("Result:", run, flush=True)

update_case_tags_and_status(db)

con = sqlite3.connect(os.environ["DB_PATH"])

print("\n===== SEMGREP SMOKE SUMMARY =====")

for row in con.execute("""
    SELECT status, COUNT(*)
    FROM scanner_runs
    WHERE scanner='semgrep'
    GROUP BY status
    ORDER BY status
"""):
    print(row)

print("Semgrep findings:", con.execute("""
    SELECT COUNT(*)
    FROM scanner_findings
    WHERE scanner='semgrep'
""").fetchone()[0])

con.close()
PY
