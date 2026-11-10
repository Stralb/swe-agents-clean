#!/bin/bash
#SBATCH --job-name=mim-revalidate
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --output=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/mim-revalidate-%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/mim-revalidate-%A_%a.err

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"

cd "$ROOT" || true

source .venv/bin/activate

if [ -f .env.cluster ]; then
    set -a
    source .env.cluster
    set +a
fi

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="$ROOT/config.agentic_js.yml"

export CODEQL_RAM_MB="${CODEQL_RAM_MB:-4096}"
export CODEQL_THREADS="${CODEQL_THREADS:-1}"

if [ -n "${SLURM_TMPDIR:-}" ]; then
    export TMPDIR="$SLURM_TMPDIR"
    export TEMP="$SLURM_TMPDIR"
    export TMP="$SLURM_TMPDIR"
fi

unset UI_READ_ONLY UI_COMMAND_SPOOL

CASE_IDS=(
    59
    290
    291
    299
    649
    3882
    4621
    5355
    8038
    8162
    8461
    9992
    10361
    10825
    15151
    15739
    16203
)

INDEX="${SLURM_ARRAY_TASK_ID:-0}"
CASE_ID="${CASE_IDS[$INDEX]}"

echo "REVALIDATION_START|case=$CASE_ID|time=$(date -u +%FT%TZ)"

python scripts/revalidate_scanner_case.py \
    --case-id "$CASE_ID"

STATUS=$?

echo "REVALIDATION_END|case=$CASE_ID|status=$STATUS|time=$(date -u +%FT%TZ)"

exit "$STATUS"
