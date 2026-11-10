#!/bin/bash
#SBATCH --job-name=evidence-hunt
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --time=23:00:00
#SBATCH --mem=96G
#SBATCH --output=/home-mscluster/%u/evidence_hunt_%j.log

set -euo pipefail

PROJECT=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
cd "$PROJECT"

source "$PROJECT/.env.cluster"
source "$PROJECT/.venv/bin/activate"

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$HOME/.local/bin:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export DB_PATH=data/miner.db

export MINER_CODEQL_TMPDIR="/tmp/$USER/miner-codeql-tmp"
export CODEQL_TMPDIR="/tmp/$USER/miner-codeql-tmp"
export CODEQL_RAM_MB=6144
export CODEQL_THREADS=2

# Critical: do not accept generic source PRs as evidence candidates.
export EVIDENCE_STRICT_SURFACE=true

mkdir -p "$MINER_CODEQL_TMPDIR"
mkdir -p logs exports

echo "--- TOOL CHECK ---"
python --version
git --version
node --version
codeql version
gitleaks version || true
osv-scanner --version || true

echo "--- CODEQL PACK CHECK ---"
codeql pack download codeql/javascript-queries
codeql pack download codeql/python-queries
codeql resolve queries codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls | head -n 10

echo "--- RESET DB ---"
make reset-db

echo "--- EVIDENCE-FIRST COLLECTION ---"
make collect \
  RETRIEVAL_MODE=targeted \
  QUERY_PHASES=combined_issue_link_stream,single_stream_high_signal \
  TARGETED_PER_PAGE=50 \
  TARGETED_MAX_PAGES=2 \
  TARGETED_MAX_TERMS=80 \
  TARGETED_PAUSE_SECONDS=10 \
  MAX_REPOS=1500 \
  MAX_CASES=600 \
  MAX_CASES_PER_REPO=2 \
  MAX_PRS=200 \
  MAX_SECONDS=21600 \
  MIN_STARS=20 \
  LOOKBACK_START=2023-01-01 \
  GITHUB_LANGUAGES=Python,JavaScript,TypeScript \
  ISSUE_MIN_BODY_CHARS=50 \
  REQUIRE_PRIMARY_WORKER=true \
  REQUIRE_HIGH_YIELD_SURFACE=true \
  MAX_CHANGED_FILES_FOR_EVIDENCE=40 \
  MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=1 \
  EXCLUDE_DOCS_SCOPE_ONLY=true \
  GITHUB_SEARCH_MIN_INTERVAL_SECONDS=2.5 \
  GITHUB_REQUEST_JITTER_SECONDS=0.8 \
  FORCE_REFRESH=false

echo "--- STATUS AFTER COLLECT ---"
python scripts/status.py || true

echo "--- SCAN: SECRETS + DEPENDENCY + CODEQL ---"
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("data/miner.db")
cur = con.cursor()
print("journal_mode:", cur.execute("PRAGMA journal_mode=WAL").fetchone())
cur.execute("PRAGMA busy_timeout=60000")
con.close()
PY

for i in $(seq 1 4); do
  (
    export MINER_WORKER_ID="evidence-${SLURM_JOB_ID}-w${i}"

    make scan \
      MODE=full \
      MAX_CASES=600 \
      CODEQL_TRIGGER=all_codeql \
      CODEQL_LANGUAGE=auto \
      CODEQL_QUERY_SUITE="codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls" \
      CODEQL_MAX_PER_RUN=1 \
      CODEQL_WORKERS=1 \
      CODEQL_BUILD_MODE=none \
      CODEQL_TIMEOUT_SECONDS=14400 \
      SCAN_CODEQL=true \
      SCAN_GITLEAKS=true \
      SCAN_OSV=true \
      SCAN_DEPENDENCY_DOWNGRADE=true \
      FORCE_RESCAN=false \
      2>&1 | sed "s/^/[worker-$i] /"
  ) &
done

wait

echo "--- FINDINGS SUMMARY ---"
python3 - <<'PY'
import sqlite3, json

con = sqlite3.connect("data/miner.db")
cur = con.cursor()

print("\n=== CASE STATUS ===")
for row in cur.execute("""
SELECT status, COUNT(*)
FROM cases
GROUP BY status
ORDER BY COUNT(*) DESC
"""):
    print(row)

print("\n=== SCANNER RUNS ===")
for row in cur.execute("""
SELECT scanner, status, COUNT(*)
FROM scanner_runs
GROUP BY scanner, status
ORDER BY scanner, status
"""):
    print(row)

print("\n=== FINDINGS SUMMARY ===")
for row in cur.execute("""
SELECT scanner, kind, COUNT(*)
FROM findings
GROUP BY scanner, kind
ORDER BY COUNT(*) DESC
"""):
    print(row)

print("\n=== EVIDENCE CASES ===")
for row in cur.execute("""
SELECT case_id, scanner, kind, COUNT(*)
FROM findings
GROUP BY case_id, scanner, kind
ORDER BY case_id, scanner, kind
LIMIT 200
"""):
    print(row)

con.close()
PY

echo "--- EXPORT ---"
python scripts/export.py || true
cp data/miner.db exports/miner.evidence.db
zip -r exports/evidence_hunt_results_${SLURM_JOB_ID}.zip data/miner.db exports logs -x "**/__pycache__/*"

echo "--- DONE ---"
