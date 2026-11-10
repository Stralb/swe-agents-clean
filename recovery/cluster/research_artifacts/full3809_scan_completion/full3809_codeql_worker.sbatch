#!/bin/bash

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"

cd "$ROOT" || true
source .venv/bin/activate 2>/dev/null || true

if [ -f .env.cluster ]; then
    set -a
    source .env.cluster
    set +a
fi

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="$ROOT/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="$RUN_DIR/spool"
export POOL_PARTITION="bigbatch"

export SLURM_TMPDIR="/var/tmp/$USER/full3809-codeql-${SLURM_ARRAY_JOB_ID}-${SLURM_ARRAY_TASK_ID}"
export TMPDIR="$SLURM_TMPDIR"
export TEMP="$SLURM_TMPDIR"
export TMP="$SLURM_TMPDIR"

mkdir -p "$SLURM_TMPDIR" || true

unset UI_READ_ONLY UI_COMMAND_SPOOL

echo "START=$(date -u +%FT%TZ)"
echo "HOST=$(hostname)"
echo "SCRATCH=$SLURM_TMPDIR"
echo "SPOOL=$DISTRIBUTED_SPOOL_ROOT"
df -h /var/tmp || true

python -m src.distributed.codeql_pipeline \
    worker \
    --idle-rounds 12 \
    --idle-seconds 10

RC=$?

echo "RETURN_CODE=$RC"
echo "END=$(date -u +%FT%TZ)"

test "$RC" -eq 0
