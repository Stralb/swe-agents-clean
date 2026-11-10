#!/bin/bash
#SBATCH --job-name=evidence-array
#SBATCH --partition=biggpu
#SBATCH --array=1-5
#SBATCH --time=3-00:00:00
#SBATCH --output=/home-mscluster/%u/evidence_array_%A_%a.log

set -euo pipefail

BASE=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
RUNROOT=/home-mscluster/$USER/new/evidence_runs
SHARD=$SLURM_ARRAY_TASK_ID
PROJECT=$RUNROOT/shard_$SHARD

echo "--- HOST ---"
hostname
echo "--- SHARD ---"
echo "$SHARD"

mkdir -p "$RUNROOT"

echo "--- PREPARE SHARD COPY ---"
rm -rf "$PROJECT"
mkdir -p "$PROJECT"

rsync -a \
  --exclude ".git" \
  --exclude ".venv" \
  --exclude "__pycache__" \
  --exclude "logs" \
  --exclude "tmp" \
  "$BASE/" "$PROJECT/"

cd "$PROJECT"

echo "--- ENV ---"
source "$BASE/.env.cluster"

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$HOME/.local/bin:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export DB_PATH=data/miner.db

export EVIDENCE_STRICT_SURFACE=true

export MINER_CODEQL_TMPDIR="/tmp/$USER/miner-codeql-${SLURM_ARRAY_JOB_ID}-${SHARD}"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"
export CODEQL_RAM_MB=4096
export CODEQL_THREADS=1

mkdir -p "$MINER_CODEQL_TMPDIR" logs exports

echo "--- TOOL CHECK ---"
python --version
git --version
node --version || true
codeql version || true
gitleaks version || true
osv-scanner --version || true

echo "--- CODEQL PACK CHECK ---"
codeql pack download codeql/javascript-queries || true
codeql pack download codeql/python-queries || true

echo "--- RESET DB FOR SHARD ---"
make reset-db

echo "--- CHOOSE SHARD CAMPAIGN ---"
case "$SHARD" in
  1)
    LANGS="JavaScript,TypeScript"
    LOOKBACK="2024-01-01"
    MIN_STARS=20
    ISSUE_CHARS=40
    MAX_CHANGED=30
    ;;
  2)
    LANGS="Python"
    LOOKBACK="2024-01-01"
    MIN_STARS=20
    ISSUE_CHARS=40
    MAX_CHANGED=30
    ;;
  3)
    LANGS="JavaScript,TypeScript"
    LOOKBACK="2023-01-01"
    MIN_STARS=5
    ISSUE_CHARS=20
    MAX_CHANGED=60
    ;;
  4)
    LANGS="Python"
    LOOKBACK="2023-01-01"
    MIN_STARS=5
    ISSUE_CHARS=20
    MAX_CHANGED=60
    ;;
  5)
    LANGS="JavaScript,TypeScript,Python"
    LOOKBACK="2022-01-01"
    MIN_STARS=1
    ISSUE_CHARS=10
    MAX_CHANGED=100
    ;;
esac

echo "LANGS=$LANGS"
echo "LOOKBACK=$LOOKBACK"
echo "MIN_STARS=$MIN_STARS"
echo "ISSUE_CHARS=$ISSUE_CHARS"
echo "MAX_CHANGED=$MAX_CHANGED"

echo "--- COLLECT EVIDENCE-LIKELY ISSUE-PR PAIRS ---"
make collect \
  RETRIEVAL_MODE=targeted \
  QUERY_PHASES=combined_issue_link_stream,single_stream_high_signal \
  TARGETED_PER_PAGE=50 \
  TARGETED_MAX_PAGES=4 \
  TARGETED_MAX_TERMS=120 \
  TARGETED_PAUSE_SECONDS=5 \
  MAX_REPOS=3000 \
  MAX_CASES=800 \
  MAX_CASES_PER_REPO=2 \
  MAX_PRS=250 \
  MAX_SECONDS=70000 \
  MIN_STARS=$MIN_STARS \
  LOOKBACK_START=$LOOKBACK \
  GITHUB_LANGUAGES=$LANGS \
  ISSUE_MIN_BODY_CHARS=$ISSUE_CHARS \
  REQUIRE_PRIMARY_WORKER=true \
  REQUIRE_HIGH_YIELD_SURFACE=true \
  MAX_CHANGED_FILES_FOR_EVIDENCE=$MAX_CHANGED \
  MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=1 \
  EXCLUDE_DOCS_SCOPE_ONLY=true \
  GITHUB_SEARCH_MIN_INTERVAL_SECONDS=2.0 \
  GITHUB_REQUEST_JITTER_SECONDS=0.5 \
  FORCE_REFRESH=false

echo "--- STATUS AFTER COLLECT ---"
python scripts/status.py || true

echo "--- ENABLE WAL ---"
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("data/miner.db")
cur = con.cursor()
print("journal_mode:", cur.execute("PRAGMA journal_mode=WAL").fetchone())
cur.execute("PRAGMA busy_timeout=60000")
con.close()
PY

echo "--- SCAN WITH MAX LOCAL WORKERS ---"

# Biggpu node: use aggressive local parallelism.
# 8 workers x CodeQL 4GB/thread 1 = aggressive but usually survivable.
for i in $(seq 1 8); do
  (
    export MINER_WORKER_ID="array-${SLURM_ARRAY_JOB_ID}-${SHARD}-w${i}"

    make scan \
      MODE=full \
      MAX_CASES=800 \
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
      2>&1 | sed "s/^/[shard-$SHARD worker-$i] /"
  ) &
done

wait

echo "--- FINAL STATUS ---"
python scripts/status.py || true

echo "--- FINDINGS SUMMARY ---"
python3 - <<'PY'
import sqlite3

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
try:
    for row in cur.execute("""
    SELECT scanner, kind, COUNT(*)
    FROM findings
    GROUP BY scanner, kind
    ORDER BY COUNT(*) DESC
    """):
        print(row)
except Exception as e:
    print("findings skipped:", e)

print("\n=== EVIDENCE CASES ===")
try:
    for row in cur.execute("""
    SELECT case_id, scanner, kind, COUNT(*)
    FROM findings
    GROUP BY case_id, scanner, kind
    ORDER BY case_id, scanner, kind
    LIMIT 200
    """):
        print(row)
except Exception as e:
    print("evidence skipped:", e)

con.close()
PY

echo "--- EXPORT SHARD ---"
python scripts/export.py || true
cp data/miner.db "exports/miner.shard_${SHARD}.db"
zip -r "$RUNROOT/evidence_shard_${SHARD}_${SLURM_ARRAY_JOB_ID}.zip" data/miner.db exports logs -x "**/__pycache__/*"

echo "--- DONE SHARD $SHARD ---"
