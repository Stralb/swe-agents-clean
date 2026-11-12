#!/bin/bash
#SBATCH --job-name=max-evidence
#SBATCH --time=1-00:00:00
#SBATCH --output=/home-mscluster/%u/max_evidence_%A_%a.log

set -euo pipefail

BASE=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
RUNROOT=/home-mscluster/$USER/new/max_evidence_runs

PARTITION=${SLURM_JOB_PARTITION:-unknown}
TASK=${SLURM_ARRAY_TASK_ID:-1}
JOB=${SLURM_ARRAY_JOB_ID:-$SLURM_JOB_ID}

PROJECT=$RUNROOT/${PARTITION}_${JOB}_${TASK}

echo "--- HOST ---"
hostname
echo "--- PARTITION=$PARTITION TASK=$TASK JOB=$JOB ---"
echo "--- PROJECT=$PROJECT ---"

mkdir -p "$RUNROOT"
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

export MINER_CODEQL_TMPDIR="/tmp/$USER/max-codeql-${PARTITION}-${JOB}-${TASK}"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"

mkdir -p "$MINER_CODEQL_TMPDIR" logs exports

echo "--- TOOL CHECK ---"
python --version
git --version
node --version || true
codeql version || true
gitleaks version || true
osv-scanner --version || true

codeql pack download codeql/javascript-queries || true
codeql pack download codeql/python-queries || true

echo "--- RESET DB ---"
make reset-db

echo "--- CAMPAIGN SELECTION ---"

# 24 campaign variants. Higher TASK means wider/looser.
CASE=$(( TASK % 24 ))

case "$CASE" in
  1)  LANGS="JavaScript";                 LOOKBACK="2024-01-01"; MIN_STARS=50; ISSUE_CHARS=60; MAX_CHANGED=30;  TERMS=100; PAGES=3 ;;
  2)  LANGS="TypeScript";                 LOOKBACK="2024-01-01"; MIN_STARS=50; ISSUE_CHARS=60; MAX_CHANGED=30;  TERMS=100; PAGES=3 ;;
  3)  LANGS="Python";                     LOOKBACK="2024-01-01"; MIN_STARS=50; ISSUE_CHARS=60; MAX_CHANGED=30;  TERMS=100; PAGES=3 ;;
  4)  LANGS="JavaScript,TypeScript";      LOOKBACK="2024-01-01"; MIN_STARS=20; ISSUE_CHARS=40; MAX_CHANGED=40;  TERMS=120; PAGES=4 ;;
  5)  LANGS="Python";                     LOOKBACK="2024-01-01"; MIN_STARS=20; ISSUE_CHARS=40; MAX_CHANGED=40;  TERMS=120; PAGES=4 ;;
  6)  LANGS="JavaScript";                 LOOKBACK="2023-01-01"; MIN_STARS=10; ISSUE_CHARS=30; MAX_CHANGED=60;  TERMS=140; PAGES=5 ;;
  7)  LANGS="TypeScript";                 LOOKBACK="2023-01-01"; MIN_STARS=10; ISSUE_CHARS=30; MAX_CHANGED=60;  TERMS=140; PAGES=5 ;;
  8)  LANGS="Python";                     LOOKBACK="2023-01-01"; MIN_STARS=10; ISSUE_CHARS=30; MAX_CHANGED=60;  TERMS=140; PAGES=5 ;;
  9)  LANGS="JavaScript,TypeScript";      LOOKBACK="2023-01-01"; MIN_STARS=5;  ISSUE_CHARS=20; MAX_CHANGED=80;  TERMS=160; PAGES=5 ;;
  10) LANGS="Python";                     LOOKBACK="2023-01-01"; MIN_STARS=5;  ISSUE_CHARS=20; MAX_CHANGED=80;  TERMS=160; PAGES=5 ;;
  11) LANGS="JavaScript";                 LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=10; MAX_CHANGED=100; TERMS=180; PAGES=6 ;;
  12) LANGS="TypeScript";                 LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=10; MAX_CHANGED=100; TERMS=180; PAGES=6 ;;
  13) LANGS="Python";                     LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=10; MAX_CHANGED=100; TERMS=180; PAGES=6 ;;
  14) LANGS="JavaScript,TypeScript";      LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=0;  MAX_CHANGED=120; TERMS=200; PAGES=6 ;;
  15) LANGS="Python";                     LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=0;  MAX_CHANGED=120; TERMS=200; PAGES=6 ;;
  16) LANGS="JavaScript";                 LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=220; PAGES=7 ;;
  17) LANGS="TypeScript";                 LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=220; PAGES=7 ;;
  18) LANGS="Python";                     LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=220; PAGES=7 ;;
  19) LANGS="JavaScript,TypeScript";      LOOKBACK="2020-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=180; TERMS=240; PAGES=7 ;;
  20) LANGS="Python";                     LOOKBACK="2020-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=180; TERMS=240; PAGES=7 ;;
  21) LANGS="JavaScript,TypeScript,Python"; LOOKBACK="2024-01-01"; MIN_STARS=0; ISSUE_CHARS=0; MAX_CHANGED=100; TERMS=240; PAGES=7 ;;
  22) LANGS="JavaScript,TypeScript,Python"; LOOKBACK="2023-01-01"; MIN_STARS=0; ISSUE_CHARS=0; MAX_CHANGED=150; TERMS=240; PAGES=7 ;;
  23) LANGS="JavaScript,TypeScript,Python"; LOOKBACK="2022-01-01"; MIN_STARS=0; ISSUE_CHARS=0; MAX_CHANGED=180; TERMS=240; PAGES=7 ;;
  0)  LANGS="JavaScript,TypeScript,Python"; LOOKBACK="2020-01-01"; MIN_STARS=0; ISSUE_CHARS=0; MAX_CHANGED=200; TERMS=260; PAGES=8 ;;
esac

echo "LANGS=$LANGS"
echo "LOOKBACK=$LOOKBACK"
echo "MIN_STARS=$MIN_STARS"
echo "ISSUE_CHARS=$ISSUE_CHARS"
echo "MAX_CHANGED=$MAX_CHANGED"
echo "TERMS=$TERMS"
echo "PAGES=$PAGES"

echo "--- COLLECT TARGETED EVIDENCE CASES ---"
make collect \
  RETRIEVAL_MODE=targeted \
  QUERY_PHASES=combined_issue_link_stream,single_stream_high_signal \
  TARGETED_PER_PAGE=50 \
  TARGETED_MAX_PAGES=$PAGES \
  TARGETED_MAX_TERMS=$TERMS \
  TARGETED_PAUSE_SECONDS=2 \
  MAX_REPOS=8000 \
  MAX_CASES=1200 \
  MAX_CASES_PER_REPO=2 \
  MAX_PRS=400 \
  MAX_SECONDS=80000 \
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

python3 - <<'PY'
import sqlite3
con = sqlite3.connect("data/miner.db")
cur = con.cursor()
print("journal_mode:", cur.execute("PRAGMA journal_mode=WAL").fetchone())
cur.execute("PRAGMA busy_timeout=60000")
con.close()
PY

echo "--- WORKER CONFIG ---"

if [ "$PARTITION" = "bigbatch" ]; then
  LOCAL_WORKERS=10
  export CODEQL_RAM_MB=3072
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "batch" ]; then
  LOCAL_WORKERS=6
  export CODEQL_RAM_MB=2048
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "stampede" ]; then
  LOCAL_WORKERS=10
  export CODEQL_RAM_MB=3072
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "biggpu" ]; then
  LOCAL_WORKERS=14
  export CODEQL_RAM_MB=3072
  export CODEQL_THREADS=1
else
  LOCAL_WORKERS=4
  export CODEQL_RAM_MB=2048
  export CODEQL_THREADS=1
fi

echo "LOCAL_WORKERS=$LOCAL_WORKERS"
echo "CODEQL_RAM_MB=$CODEQL_RAM_MB"
echo "CODEQL_THREADS=$CODEQL_THREADS"

echo "--- SCAN ---"

for i in $(seq 1 "$LOCAL_WORKERS"); do
  (
    export MINER_WORKER_ID="${PARTITION}-${JOB}-${TASK}-w${i}"

    make scan \
      MODE=full \
      MAX_CASES=1200 \
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
      2>&1 | sed "s/^/[${PARTITION} task-${TASK} worker-${i}] /"
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

print("\nCASE STATUS")
for r in cur.execute("""
SELECT status, COUNT(*)
FROM cases
GROUP BY status
ORDER BY COUNT(*) DESC
"""):
    print(r)

print("\nSCANNER RUNS")
for r in cur.execute("""
SELECT scanner, status, COUNT(*)
FROM scanner_runs
GROUP BY scanner, status
ORDER BY scanner, status
"""):
    print(r)

print("\nFINDINGS")
try:
    for r in cur.execute("""
    SELECT scanner, kind, COUNT(*)
    FROM findings
    GROUP BY scanner, kind
    ORDER BY COUNT(*) DESC
    """):
        print(r)
except Exception as e:
    print("findings skipped:", e)

print("\nEVIDENCE CASES")
try:
    for r in cur.execute("""
    SELECT case_id, scanner, kind, COUNT(*)
    FROM findings
    GROUP BY case_id, scanner, kind
    ORDER BY case_id, scanner, kind
    LIMIT 200
    """):
        print(r)
except Exception as e:
    print("evidence skipped:", e)

con.close()
PY

echo "--- EXPORT ---"
python scripts/export.py || true
cp data/miner.db "exports/miner.${PARTITION}.${TASK}.db"
zip -r "$RUNROOT/evidence_${PARTITION}_${JOB}_${TASK}.zip" data/miner.db exports logs -x "**/__pycache__/*"

echo "--- DONE ${PARTITION} TASK ${TASK} ---"
