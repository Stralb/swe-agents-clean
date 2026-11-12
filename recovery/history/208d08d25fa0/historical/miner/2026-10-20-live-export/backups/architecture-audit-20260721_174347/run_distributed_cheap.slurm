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
export DISTRIBUTED_SPOOL_ROOT="${DISTRIBUTED_SPOOL_ROOT:-$ROOT/data/distributed_spool}"

MODE="${DISTRIBUTED_MODE:-worker}"

if [ "$MODE" = "coordinator" ]; then
    python -m src.distributed.cheap_pipeline \
        coordinator \
        --interval 10
else
    python -m src.distributed.cheap_pipeline \
        worker \
        --idle-rounds 12 \
        --idle-seconds 10
fi
