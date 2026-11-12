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
export CONFIG="${CONFIG:-$ROOT/config.agentic_js.yml}"
export DISTRIBUTED_SPOOL_ROOT="${DISTRIBUTED_SPOOL_ROOT:-$ROOT/data/distributed_spool}"
unset UI_READ_ONLY UI_COMMAND_SPOOL

python -m src.distributed.mining_pipeline worker --idle-seconds 20 --max-idle-cycles 3
