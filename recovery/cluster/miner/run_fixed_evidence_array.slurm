#!/bin/bash
#SBATCH --job-name=fixed-evidence
#SBATCH --time=1-00:00:00
#SBATCH --output=/home-mscluster/%u/fixed_evidence_%A_%a.log

set -euo pipefail

BASE=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
RUNROOT=/home-mscluster/$USER/new/fixed_evidence_runs

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
  --exclude "data" \
  "$BASE/" "$PROJECT/"

cd "$PROJECT"

mkdir -p data/cache/github_api logs exports

source "$BASE/.env.cluster"

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip >/dev/null
pip install -r requirements.txt >/dev/null

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$HOME/.local/bin:$PATH"
export PYTHONPATH=.
export DB_PATH="/data/miner.db"
export CONFIG=config.runtime.yml
export EVIDENCE_STRICT_SURFACE=true

export MINER_CODEQL_TMPDIR="/tmp/$USER/fixed-codeql-${PARTITION}-${JOB}-${TASK}"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"

mkdir -p "$MINER_CODEQL_TMPDIR"

echo "--- TOOL CHECK ---"
python --version
git --version
node --version || true
codeql version || true
gitleaks version || true
osv-scanner --version || true

codeql pack download codeql/javascript-queries || true
codeql pack download codeql/python-queries || true

echo "--- CAMPAIGN SELECTION ---"

CASE=$(( TASK % 12 ))

case "$CASE" in
  1)  LANG="JavaScript"; LOOKBACK="2024-01-01"; MIN_STARS=20; ISSUE_CHARS=30; MAX_CHANGED=50;  TERMS=100; PAGES=3 ;;
  2)  LANG="TypeScript"; LOOKBACK="2024-01-01"; MIN_STARS=20; ISSUE_CHARS=30; MAX_CHANGED=50;  TERMS=100; PAGES=3 ;;
  3)  LANG="Python";     LOOKBACK="2024-01-01"; MIN_STARS=20; ISSUE_CHARS=30; MAX_CHANGED=50;  TERMS=100; PAGES=3 ;;
  4)  LANG="JavaScript"; LOOKBACK="2023-01-01"; MIN_STARS=5;  ISSUE_CHARS=10; MAX_CHANGED=90;  TERMS=140; PAGES=4 ;;
  5)  LANG="TypeScript"; LOOKBACK="2023-01-01"; MIN_STARS=5;  ISSUE_CHARS=10; MAX_CHANGED=90;  TERMS=140; PAGES=4 ;;
  6)  LANG="Python";     LOOKBACK="2023-01-01"; MIN_STARS=5;  ISSUE_CHARS=10; MAX_CHANGED=90;  TERMS=140; PAGES=4 ;;
  7)  LANG="JavaScript"; LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=180; PAGES=5 ;;
  8)  LANG="TypeScript"; LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=180; PAGES=5 ;;
  9)  LANG="Python";     LOOKBACK="2022-01-01"; MIN_STARS=1;  ISSUE_CHARS=0;  MAX_CHANGED=150; TERMS=180; PAGES=5 ;;
  10) LANG="JavaScript"; LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=220; TERMS=220; PAGES=6 ;;
  11) LANG="TypeScript"; LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=220; TERMS=220; PAGES=6 ;;
  0)  LANG="Python";     LOOKBACK="2021-01-01"; MIN_STARS=0;  ISSUE_CHARS=0;  MAX_CHANGED=220; TERMS=220; PAGES=6 ;;
esac

echo "LANG=$LANG"
echo "LOOKBACK=$LOOKBACK"
echo "MIN_STARS=$MIN_STARS"
echo "ISSUE_CHARS=$ISSUE_CHARS"
echo "MAX_CHANGED=$MAX_CHANGED"
echo "TERMS=$TERMS"
echo "PAGES=$PAGES"

echo "--- WRITE RUNTIME CONFIG ---"
python3 - <<PY
import yaml
from pathlib import Path

base = yaml.safe_load(Path("config.yml").read_text()) or {}

base.setdefault("database", {})["path"] = "data/miner.db"

base.setdefault("github", {})
base["github"]["language"] = "$LANG"
base["github"]["languages"] = ["$LANG"]
base["github"]["min_stars"] = int("$MIN_STARS")
base["github"]["per_page"] = 50

base.setdefault("cache", {})
base["cache"]["github_api"] = True
base["cache"]["force_refresh"] = True

base.setdefault("collection", {})
c = base["collection"]
c["retrieval_mode"] = "targeted"
c["query_phases"] = [
    "combined_issue_link_stream",
    "issue_link_baseline",
    "single_stream_high_signal",
]
c["lookback_start"] = "$LOOKBACK"
c["targeted_per_page"] = 50
c["targeted_max_pages"] = int("$PAGES")
c["targeted_max_pages_total"] = int("$PAGES")
c["targeted_max_terms"] = int("$TERMS")
c["targeted_pause_seconds"] = 8
c["require_primary_worker"] = False
c["require_high_yield_surface"] = True
c["max_changed_files_for_evidence"] = int("$MAX_CHANGED")
c["max_linked_issues_per_pr_for_evidence"] = 1
c["active_repo_seed"] = False

base.setdefault("filters", {})
base["filters"]["issue_min_body_chars"] = int("$ISSUE_CHARS")
base["filters"]["exclude_docs_scope_only"] = True

base.setdefault("scanners", {})
base["scanners"]["codeql"] = True
base["scanners"]["gitleaks"] = True
base["scanners"]["osv"] = True
base["scanners"]["dependency_downgrade"] = True
base["scanners"]["codeql_trigger"] = "all_codeql"
base["scanners"]["codeql_language"] = "auto"
base["scanners"]["codeql_timeout_seconds"] = 14400
base["scanners"]["codeql_build_mode"] = "none"

Path("config.runtime.yml").write_text(yaml.safe_dump(base, sort_keys=False))
print(Path("config.runtime.yml").read_text()[:2500])
PY

echo "--- INIT EMPTY DB ---"
python scripts/init_db.py

echo "--- COLLECT ---"
python scripts/collect.py

echo "--- RAW COUNTS AFTER COLLECT ---"
python3 - <<'PY'
import sqlite3

con = sqlite3.connect("data/miner.db")
cur = con.cursor()

for t in ["repos", "issues", "pull_requests", "cases", "excluded_cases", "retrieval_queries"]:
    try:
        print(t, cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    except Exception as e:
        print(t, e)

con.close()
PY

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

echo "--- WORKER CONFIG ---"

if [ "$PARTITION" = "bigbatch" ]; then
  LOCAL_WORKERS=8
  export CODEQL_RAM_MB=3072
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "batch" ]; then
  LOCAL_WORKERS=4
  export CODEQL_RAM_MB=2048
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "stampede" ]; then
  LOCAL_WORKERS=8
  export CODEQL_RAM_MB=3072
  export CODEQL_THREADS=1
elif [ "$PARTITION" = "biggpu" ]; then
  LOCAL_WORKERS=12
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
    python scripts/scan.py 2>&1 | sed "s/^/[${PARTITION} task-${TASK} worker-${i}] /"
  ) &
done

wait

echo "--- FINAL SUMMARY ---"
python scripts/status.py || true

python3 - <<'PY'
import sqlite3

con = sqlite3.connect("data/miner.db")
cur = con.cursor()

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

con.close()
PY

echo "--- EXPORT ---"
python scripts/export.py || true
cp data/miner.db "exports/miner.${PARTITION}.${TASK}.db"
zip -r "$RUNROOT/fixed_evidence_${PARTITION}_${JOB}_${TASK}.zip" data/miner.db config.runtime.yml exports logs -x "**/__pycache__/*"

echo "--- DONE ${PARTITION} TASK ${TASK} ---"
