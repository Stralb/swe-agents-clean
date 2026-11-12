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
export CONFIG="$ROOT/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="$ROOT/data/distributed_spool"

if [ -n "${SLURM_TMPDIR:-}" ]; then
    export TMPDIR="$SLURM_TMPDIR"
    export TEMP="$SLURM_TMPDIR"
    export TMP="$SLURM_TMPDIR"
fi

python -m src.distributed.codeql_pipeline \
    worker \
    --idle-rounds 12 \
    --idle-seconds 10
