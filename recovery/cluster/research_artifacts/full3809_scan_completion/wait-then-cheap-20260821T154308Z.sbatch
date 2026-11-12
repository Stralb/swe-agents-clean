#!/bin/bash
#SBATCH --partition=stampede
#SBATCH --time=2-23:50:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --signal=B:TERM@300

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
SPOOL="$ROOT/data/distributed_spool"

cd "$ROOT" || true
source .venv/bin/activate 2>/dev/null || true

export DISTRIBUTED_SPOOL_ROOT="$SPOOL"
export CONFIG="$ROOT/config.agentic_js.yml"

echo "WAIT_WORKER_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "TYPE=cheap"
echo "HOST=$(hostname)"

for attempt in $(seq 1 720); do

    PENDING="$(
        find "$SPOOL/cheap_analysis/pending" \
          -maxdepth 1 \
          -type f \
          -name '*.json' \
          2>/dev/null |
        wc -l
    )"

    echo "attempt=$attempt pending=$PENDING"

    if [ "$PENDING" -gt 0 ]; then
        echo "STARTING_CHEAP_ANALYSIS"
        bash "$ROOT/run_distributed_cheap.slurm"
        RC=$?
        echo "CHEAP_WORKER_RC=$RC"
        break
    fi

    sleep 10
done
