#!/bin/bash
#SBATCH --job-name=prfirst-long
#SBATCH --partition=bigbatch
#SBATCH --time=07:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home-mscluster/%u/prfirst_long_collect_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster
source .current_prfirst_longrun_db

export PYTHONPATH=.
export CONFIG=config.yml

# PR-first long-run collection settings
export LOOKBACK_START=2025-01-01
export MAX_REPOS=500
export MAX_PRS=500
export MAX_CASES=2000
export MAX_CASES_PER_REPO=20
export MAX_SECONDS=25200

# Make discovery less restrictive
export ACTIVE_REPO_SEED=true
export ACTIVE_REPO_SEED_MAX_PAGES=8
export ACTIVE_REPO_SEED_PER_PAGE=100

export REPO_MONTH_PER_PAGE=100
export REPO_MONTH_MAX_PAGES=8
export REPO_WINDOW_PER_PAGE=100
export REPO_WINDOW_MAX_PAGES=8
export REPO_WINDOW_SPLIT_THRESHOLD=80
export REPO_WINDOW_EXHAUSTIVE_SPLIT=true

# Do not over-filter evidence during first PR-first run
export MAX_CHANGED_FILES_FOR_EVIDENCE=150
export MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=3
export ISSUE_MIN_BODY_CHARS=0
export EXCLUDE_DOCS_SCOPE_ONLY=false
export REQUIRE_PRIMARY_WORKER=false
export REQUIRE_HIGH_YIELD_SURFACE=false

# Rate limit safety
export GITHUB_MIN_REMAINING=100
export GITHUB_SEARCH_MIN_REMAINING=20
export GITHUB_SEARCH_MIN_INTERVAL_SECONDS=3
export GITHUB_CORE_MIN_INTERVAL_SECONDS=1
export GITHUB_REQUEST_JITTER_SECONDS=1

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "DB_PATH=$DB_PATH"
echo "START=$(date)"

echo "===== VERIFY DB ====="
make methodology-status || true

echo "===== START PR-FIRST COLLECTION ====="
make collect-pr-first

echo "===== PROFILE AFTER COLLECTION ====="
make methodology-profile
make methodology-status
make region-yield

echo "END=$(date)"
