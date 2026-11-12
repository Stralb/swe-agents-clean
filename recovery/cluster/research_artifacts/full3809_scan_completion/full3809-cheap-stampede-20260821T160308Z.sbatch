#!/bin/bash
#SBATCH --partition=stampede
#SBATCH --time=1-00:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --signal=B:TERM@300

ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"

cd "$ROOT" || true
source .venv/bin/activate 2>/dev/null || true

export DISTRIBUTED_SPOOL_ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"
export CONFIG="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/config.agentic_js.yml"

# Stampede /tmp is only ~31 GB.
# Use its much larger local /var/tmp instead.
export SLURM_TMPDIR="/var/tmp/$USER/full3809-cheap-$SLURM_JOB_ID"
export TMPDIR="$SLURM_TMPDIR"

mkdir -p "$SLURM_TMPDIR" || true

echo "START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "HOST=$(hostname)"
echo "SLURM_TMPDIR=$SLURM_TMPDIR"

bash "$ROOT/run_distributed_cheap.slurm"
RC=$?

echo "RETURN_CODE=$RC"

test "$RC" -eq 0
