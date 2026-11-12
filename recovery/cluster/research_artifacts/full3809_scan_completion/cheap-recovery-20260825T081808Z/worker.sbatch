#!/bin/bash
#SBATCH --partition=bigbatch
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

export SLURM_TMPDIR="/var/tmp/$USER/full3809-recovery-$SLURM_JOB_ID"
export TMPDIR="$SLURM_TMPDIR"

mkdir -p "$SLURM_TMPDIR" || true

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "JOB=$SLURM_JOB_ID"
echo "HOST=$(hostname)"
echo "TMP=$SLURM_TMPDIR"
echo "SOURCE_DB=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"

bash "$ROOT/run_distributed_cheap.slurm"

RC=$?

echo "WORKER_RC=$RC"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test "$RC" -eq 0
