#!/bin/bash
#SBATCH --time=1-00:00:00
#SBATCH --requeue
#SBATCH --signal=B:USR1@600

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
SELF_SCRIPT="$ROOT/run_pool_autoscaler.slurm"
SERVICE_NAME="pool-autoscaler"
SUCCESSOR_SUBMITTED=0

schedule_successor() {
    if [ "$SUCCESSOR_SUBMITTED" = "1" ]; then
        return
    fi

    for ATTEMPT in 1 2 3; do
        SUBMISSION="$(
            sbatch --parsable \
                --partition="${SLURM_JOB_PARTITION:-batch}" \
                --time=1-00:00:00 \
                --requeue \
                --signal=B:USR1@600 \
                --dependency="afterany:${SLURM_JOB_ID}" \
                --job-name="$SERVICE_NAME" \
                --output="$ROOT/logs/${SERVICE_NAME}-%j.out" \
                --error="$ROOT/logs/${SERVICE_NAME}-%j.err" \
                "$SELF_SCRIPT" 2>&1
        )"

        SUCCESSOR_JOB="${SUBMISSION%%;*}"

        if printf '%s\n' "$SUCCESSOR_JOB" | grep -Eq '^[0-9]+$'; then
            SUCCESSOR_SUBMITTED=1
            echo "SUCCESSOR_SUBMITTED|current=$SLURM_JOB_ID|next=$SUCCESSOR_JOB"
            return
        fi

        echo "SUCCESSOR_ATTEMPT_FAILED|attempt=$ATTEMPT|message=$SUBMISSION"
        sleep 5
    done

    echo "SUCCESSOR_FAILED|current=$SLURM_JOB_ID"
}

trap schedule_successor USR1

if cd "$ROOT"; then
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
CRASH_COUNT=0

while :; do
    echo "SERVICE_START|name=$SERVICE_NAME|time=$(date -u +%FT%TZ)"

    python -m src.distributed.pool_autoscaler --interval 30 &
    SERVICE_PID=$!
    SERVICE_STATUS=0

    while kill -0 "$SERVICE_PID" 2>/dev/null; do
        wait "$SERVICE_PID"
        SERVICE_STATUS=$?
    done

    CRASH_COUNT=$((CRASH_COUNT + 1))

    echo "SERVICE_RESTART|name=$SERVICE_NAME|status=$SERVICE_STATUS|count=$CRASH_COUNT"
    sleep 15
done
fi
