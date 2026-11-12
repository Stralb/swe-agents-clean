#!/bin/bash

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

python -m src.workers.controlled_daemon \
    --daemon "$DAEMON_NAME" \
    --generation "$DAEMON_GENERATION" \
    --idle-seconds "${DAEMON_IDLE_SECONDS:-10}"
