#!/bin/bash
#SBATCH --job-name=prfirst-slow
#SBATCH --partition=bigbatch
#SBATCH --time=07:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=/home-mscluster/%u/prfirst_slow_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster
source .current_prfirst_longrun_db

export PYTHONPATH=.
export CONFIG=config.yml

# Wider window
export LOOKBACK_START=2025-01-01

# Larger target
export MAX_REPOS=1000
export MAX_PRS=1000
export MAX_CASES=3000
export MAX_CASES_PER_REPO=20
export MAX_SECONDS=25200

# PR-first repo discovery
export ACTIVE_REPO_SEED=true
export ACTIVE_REPO_SEED_MAX_PAGES=20
export ACTIVE_REPO_SEED_PER_PAGE=50

# Slower per-window search to avoid secondary limit
export REPO_MONTH_PER_PAGE=50
export REPO_MONTH_MAX_PAGES=6
export REPO_WINDOW_PER_PAGE=50
export REPO_WINDOW_MAX_PAGES=6
export REPO_WINDOW_SPLIT_THRESHOLD=60
export REPO_WINDOW_EXHAUSTIVE_SPLIT=true

# Broader language pool
export GITHUB_LANGUAGES="Python,JavaScript,TypeScript,Go,Ruby,Java,PHP,Shell"

# Relax filters for PR-first discovery
export MAX_CHANGED_FILES_FOR_EVIDENCE=150
export MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE=3
export ISSUE_MIN_BODY_CHARS=0
export EXCLUDE_DOCS_SCOPE_ONLY=false
export REQUIRE_PRIMARY_WORKER=false
export REQUIRE_HIGH_YIELD_SURFACE=false

# Important: slow GitHub down instead of exiting early
export GITHUB_MIN_REMAINING=100
export GITHUB_SEARCH_MIN_REMAINING=25
export GITHUB_SEARCH_MIN_INTERVAL_SECONDS=12
export GITHUB_CORE_MIN_INTERVAL_SECONDS=2
export GITHUB_REQUEST_JITTER_SECONDS=3
export MAX_SECONDARY_RETRIES=20
export SECONDARY_WAIT_SECONDS=90
export SEARCH_PAUSE_SECONDS=8

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "DB_PATH=$DB_PATH"
echo "START=$(date)"

echo "===== BEFORE ====="
make methodology-status || true
make region-yield || true

echo "===== CONTINUE PR-FIRST COLLECTION SLOW ====="
make collect-pr-first

echo "===== AFTER ====="
make methodology-profile
make methodology-status
make region-yield

echo "END=$(date)"
