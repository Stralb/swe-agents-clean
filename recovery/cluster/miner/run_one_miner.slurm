#!/bin/bash
#SBATCH --job-name=one-miner
#SBATCH --partition=batch
#SBATCH --time=1-00:00:00
#SBATCH --output=/home-mscluster/%u/one_miner_%j.log

set -euo pipefail

PROJECT=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
cd "$PROJECT"

source "$PROJECT/.env.cluster"
source "$PROJECT/.venv/bin/activate"

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export DB_PATH="$PROJECT/data/miner.db"
export PYTHON=./.venv/bin/python

echo "--- ONE MINER START ---"
hostname
which python
python --version
python -c "import dotenv; print('dotenv ok')"

echo "--- DB CHECK ---"
python - <<'PY'
import sqlite3, os
db = os.environ["DB_PATH"]
con = sqlite3.connect(db)
cur = con.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("db:", db)
print("tables:", tables)
assert "cases" in tables
assert "scanner_jobs" in tables
print("journal_mode:", cur.execute("PRAGMA journal_mode=WAL").fetchone())
cur.execute("PRAGMA busy_timeout=60000")
con.close()
PY

# One miner only.
export GITHUB_WORKERS=1
export SOURCE_WORKERS=0
export DEP_WORKERS=0
export SECRET_WORKERS=0
export CODEQL_WORKERS=0

# Critical: do not kill everything at repo_filter.
export MIN_STARS=0

# Structural mining.
export RETRIEVAL_MODE=repo_window_pr_search
export GITHUB_LANGUAGES=Python,JavaScript,TypeScript
export LOOKBACK_START=2023-01-01

# Keep this permissive until we prove case creation.
export ISSUE_MIN_BODY_CHARS=20
export REQUIRE_PRIMARY_WORKER=false
export REQUIRE_HIGH_YIELD_SURFACE=true
export EXCLUDE_DOCS_SCOPE_ONLY=true
export MAX_CHANGED_FILES_FOR_EVIDENCE=150
export MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=1

# Limits.
export MAX_REPOS=500
export MAX_PRS=300
export MAX_CASES=1000
export MAX_CASES_PER_REPO=3
export MAX_SECONDS=7200

# GitHub pacing.
export GITHUB_CACHE=true
export FORCE_REFRESH=false
export GITHUB_SEARCH_MIN_INTERVAL_SECONDS=6
export GITHUB_CORE_MIN_INTERVAL_SECONDS=0
export GITHUB_REQUEST_JITTER_SECONDS=1
export GITHUB_SEARCH_MIN_REMAINING=1
export GITHUB_MIN_REMAINING=100

# Active seed and repo window.
export ACTIVE_REPO_SEED=true
export ACTIVE_REPO_SEED_MAX_PAGES=10
export ACTIVE_REPO_SEED_PER_PAGE=100
export REPO_WINDOW_PER_PAGE=100
export REPO_WINDOW_MAX_PAGES=8
export REPO_WINDOW_EXHAUSTIVE_SPLIT=false

python scripts/check_github_auth.py || true
python scripts/status.py || true

make mine \
  MIN_STARS=$MIN_STARS \
  GITHUB_WORKERS=1 \
  SOURCE_WORKERS=0 \
  DEP_WORKERS=0 \
  SECRET_WORKERS=0 \
  CODEQL_WORKERS=0 \
  MAX_REPOS=$MAX_REPOS \
  MAX_PRS=$MAX_PRS \
  MAX_CASES=$MAX_CASES \
  MAX_SECONDS=$MAX_SECONDS \
  MAX_CASES_PER_REPO=$MAX_CASES_PER_REPO \
  RETRIEVAL_MODE=$RETRIEVAL_MODE \
  GITHUB_LANGUAGES=$GITHUB_LANGUAGES \
  LOOKBACK_START=$LOOKBACK_START \
  ISSUE_MIN_BODY_CHARS=$ISSUE_MIN_BODY_CHARS \
  REQUIRE_PRIMARY_WORKER=$REQUIRE_PRIMARY_WORKER \
  REQUIRE_HIGH_YIELD_SURFACE=$REQUIRE_HIGH_YIELD_SURFACE \
  EXCLUDE_DOCS_SCOPE_ONLY=$EXCLUDE_DOCS_SCOPE_ONLY \
  MAX_CHANGED_FILES_FOR_EVIDENCE=$MAX_CHANGED_FILES_FOR_EVIDENCE \
  MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=$MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE \
  ACTIVE_REPO_SEED=$ACTIVE_REPO_SEED \
  ACTIVE_REPO_SEED_MAX_PAGES=$ACTIVE_REPO_SEED_MAX_PAGES \
  ACTIVE_REPO_SEED_PER_PAGE=$ACTIVE_REPO_SEED_PER_PAGE \
  REPO_WINDOW_PER_PAGE=$REPO_WINDOW_PER_PAGE \
  REPO_WINDOW_MAX_PAGES=$REPO_WINDOW_MAX_PAGES \
  REPO_WINDOW_EXHAUSTIVE_SPLIT=$REPO_WINDOW_EXHAUSTIVE_SPLIT \
  GITHUB_SEARCH_MIN_INTERVAL_SECONDS=$GITHUB_SEARCH_MIN_INTERVAL_SECONDS \
  GITHUB_CORE_MIN_INTERVAL_SECONDS=$GITHUB_CORE_MIN_INTERVAL_SECONDS \
  GITHUB_REQUEST_JITTER_SECONDS=$GITHUB_REQUEST_JITTER_SECONDS
