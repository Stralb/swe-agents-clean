#!/bin/bash
#SBATCH --partition=batch
#SBATCH --time=23:50:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --signal=B:TERM@300
#SBATCH --output=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/codeql37-%A_%a.out
#SBATCH --error=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/codeql37-%A_%a.err

cd "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart" || true
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart:${PYTHONPATH:-}"
export CONFIG="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"

export SLURM_TMPDIR="/var/tmp/$USER/codeql37-$SLURM_JOB_ID-${SLURM_ARRAY_TASK_ID:-0}"
export TMPDIR="$SLURM_TMPDIR"

mkdir -p "$SLURM_TMPDIR" || true

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "JOB=$SLURM_JOB_ID"
echo "ARRAY=${SLURM_ARRAY_TASK_ID:-0}"
echo "HOST=$(hostname)"
echo "TMP=$SLURM_TMPDIR"
echo "SOURCE_DB=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"

bash "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/run_distributed_codeql.slurm"

RC=$?

echo "WORKER_RC=$RC"
echo "END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

test "$RC" -eq 0
