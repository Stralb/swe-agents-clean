#!/bin/bash
#SBATCH --time=2-23:50:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --signal=B:TERM@300

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
SPOOL="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"

cd "$ROOT" || true
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH="$ROOT:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="$ROOT/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="$SPOOL"

# Both node types have enough persistent local /var/tmp.
export SLURM_TMPDIR="/var/tmp/$USER/full3809-cheap-$SLURM_JOB_ID"
export TMPDIR="$SLURM_TMPDIR"

mkdir -p "$SLURM_TMPDIR" || true

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "JOB=$SLURM_JOB_ID"
echo "HOST=$(hostname)"
echo "TMP=$SLURM_TMPDIR"

bash "$ROOT/run_distributed_cheap.slurm"

RC=$?

echo "WORKER_RC=$RC"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test "$RC" -eq 0
