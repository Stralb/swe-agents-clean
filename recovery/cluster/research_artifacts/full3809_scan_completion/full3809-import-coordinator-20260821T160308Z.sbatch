#!/bin/bash
#SBATCH --job-name=full3809-coord
#SBATCH --partition=bigbatch
#SBATCH --time=2-00:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --signal=B:TERM@300
#SBATCH --output=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/full3809-import-coord-%j.out
#SBATCH --error=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/full3809-import-coord-%j.err

cd "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart" || true
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"

# Deliberately prevents giant coordinator snapshots.
# Tasks were explicitly seeded above.
export SNAPSHOT_PUBLICATION_ENABLED=0

python -m src.distributed.local_coordinator --interval 5
