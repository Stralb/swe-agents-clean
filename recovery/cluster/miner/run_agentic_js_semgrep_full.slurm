#!/bin/bash
#SBATCH --job-name=semgrep-full
#SBATCH --output=logs/semgrep-full-%j.out
#SBATCH --error=logs/semgrep-full-%j.err
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
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

echo "DB_PATH=$DB_PATH"
semgrep --version

python - <<'PY'
import os
import sqlite3
import traceback

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
    ORDER BY c.id
""")

print("Remaining Semgrep cases:", len(cases), flush=True)

for index, case in enumerate(cases, start=1):
    case_id = int(case["case_id"])
    pr_id = int(case["pr_id"])

    print(
        "[%s/%s] case=%s repo=%s pr=%s"
        % (
            index,
            len(cases),
            case_id,
            case["repo_full_name"],
            case["pr_number"],
        ),
        flush=True,
    )

    try:
        scan_case(db, case, config)
    except Exception as exc:
        traceback.print_exc()

        db.execute("""
            INSERT INTO scanner_runs(
                case_id,
                pr_id,
                scanner,
                status,
                finished_at,
                stdout,
                stderr
            )
            VALUES (
                ?,
                ?,
                'semgrep',
                'error',
                CURRENT_TIMESTAMP,
                '',
                ?
            )
        """, (case_id, pr_id, str(exc)[:5000]))

    run = db.one("""
        SELECT status, stdout, stderr
        FROM scanner_runs
        WHERE case_id = ?
          AND scanner = 'semgrep'
        ORDER BY id DESC
        LIMIT 1
    """, (case_id,))

    if not run:
        raise RuntimeError(
            "Semgrep produced no scanner record for case %s"
            % case_id
        )

    print(
        "  status=%s stdout=%s stderr=%s"
        % (
            run["status"],
            str(run.get("stdout") or "")[:160],
            str(run.get("stderr") or "")[:160],
        ),
        flush=True,
    )

update_case_tags_and_status(db)

con = sqlite3.connect(os.environ["DB_PATH"])

print("\n===== SEMGREP FULL SUMMARY =====")

for row in con.execute("""
    SELECT status, COUNT(*)
    FROM scanner_runs
    WHERE scanner = 'semgrep'
    GROUP BY status
    ORDER BY status
"""):
    print(row)

total = con.execute("""
    SELECT COUNT(DISTINCT case_id)
    FROM scanner_runs
    WHERE scanner = 'semgrep'
""").fetchone()[0]

findings = con.execute("""
    SELECT COUNT(*)
    FROM scanner_findings
    WHERE scanner = 'semgrep'
""").fetchone()[0]

missing = con.execute("""
    SELECT COUNT(*)
    FROM cases c
    WHERE NOT EXISTS (
        SELECT 1
        FROM scanner_runs sr
        WHERE sr.case_id = c.id
          AND sr.scanner = 'semgrep'
    )
""").fetchone()[0]

print("Cases recorded:", total)
print("Findings:", findings)
print("Missing cases:", missing)

con.close()

if missing:
    raise SystemExit(
        "Semgrep ended with %s missing cases" % missing
    )
PY
