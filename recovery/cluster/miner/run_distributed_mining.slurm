#!/bin/bash

# BEGIN MINING GITHUB AUTH
MINER_ENV="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/.env.cluster"
if [ -f "$MINER_ENV" ]; then
    set -a
    . "$MINER_ENV"
    set +a
fi
# END MINING GITHUB AUTH

# BEGIN ACTIVE REPOSITORY SEED
REPO_SEED_POINTER="$ROOT/.current_agentic_js_eval_db"

if [ -f "$REPO_SEED_POINTER" ]; then
    MINING_REPO_SEED_DB="$(
        tr -d '[:space:]' \
            < "$REPO_SEED_POINTER" \
            2>/dev/null
    )"

    case "$MINING_REPO_SEED_DB" in
        /*)
            ;;
        "")
            ;;
        *)
            MINING_REPO_SEED_DB="$ROOT/$MINING_REPO_SEED_DB"
            ;;
    esac

    if [ -n "$MINING_REPO_SEED_DB" ] \
       && [ -f "$MINING_REPO_SEED_DB" ]; then
        export MINING_REPO_SEED_DB
    fi
fi
# END ACTIVE REPOSITORY SEED


set -euo pipefail
ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$ROOT"
mkdir -p logs
source .venv/bin/activate
if [ -f .env.cluster ]; then
    set -a
    source .env.cluster
    set +a
fi
export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="${CONFIG:-$ROOT/config.agentic_js.yml}"
export DISTRIBUTED_SPOOL_ROOT="${DISTRIBUTED_SPOOL_ROOT:-$ROOT/data/distributed_spool}"
unset UI_READ_ONLY UI_COMMAND_SPOOL

python -m src.distributed.mining_pipeline worker --idle-seconds 20 --max-idle-cycles 180
