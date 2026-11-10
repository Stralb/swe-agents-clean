#!/bin/bash
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
export CONFIG="$ROOT/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="$ROOT/data/distributed_spool"

unset UI_READ_ONLY UI_COMMAND_SPOOL

COORDINATOR_PID=""
AUTOSCALER_PID=""

cleanup() {
    set +e

    if [ -n "$COORDINATOR_PID" ]; then
        kill -TERM "$COORDINATOR_PID" 2>/dev/null || true
    fi

    if [ -n "$AUTOSCALER_PID" ]; then
        kill -TERM "$AUTOSCALER_PID" 2>/dev/null || true
    fi

    wait "$COORDINATOR_PID" 2>/dev/null || true
    wait "$AUTOSCALER_PID" 2>/dev/null || true
}

trap 'cleanup; exit 0' TERM INT

python -m src.distributed.local_coordinator \
    --interval 5 &

COORDINATOR_PID="$!"

python -m src.distributed.pool_autoscaler \
    --interval 20 &

AUTOSCALER_PID="$!"

set +e
wait -n
STATUS="$?"
set -e

cleanup
exit "$STATUS"
