#!/bin/bash
#SBATCH --job-name=eval-existing
#SBATCH --partition=biggpu
#SBATCH --time=1-00:00:00
#SBATCH --output=/home-mscluster/%u/eval_existing_%j.log

set -euo pipefail

PROJECT=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
cd "$PROJECT"

source "$PROJECT/.env.cluster"
source "$PROJECT/.venv/bin/activate"

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export PYTHON=./.venv/bin/python

# --- LOCAL SCRATCH SETUP ---
# Create unique temp directories on the compute node
export MINER_WORKER_ID="eval-${SLURM_JOB_ID}"
export MINER_CODEQL_TMPDIR="/tmp/$USER/codeql-${SLURM_JOB_ID}"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"
export LOCAL_DB_DIR="/tmp/$USER/db-${SLURM_JOB_ID}"

mkdir -p "$MINER_CODEQL_TMPDIR"
mkdir -p "$LOCAL_DB_DIR"

# Copy the database from the network drive to the local compute node
cp "$PROJECT/data/miner.db" "$LOCAL_DB_DIR/miner.db"
export DB_PATH="$LOCAL_DB_DIR/miner.db"

# Guarantee the DB gets copied back, even if the script crashes!
cleanup() {
    echo "Job finished or interrupted. Syncing database back to NFS..."
    cp "$LOCAL_DB_DIR/miner.db" "$PROJECT/data/miner.db"
    echo "Database sync complete!"
}
trap cleanup EXIT
# ---------------------------

make evaluate \
  GITHUB_WORKERS=0 \
  SOURCE_WORKERS=1 \
  DEP_WORKERS=1 \
  SECRET_WORKERS=1 \
  CODEQL_WORKERS=1 \
  SCAN_CODEQL=true \
  SCAN_GITLEAKS=true \
  SCAN_OSV=true \
  SCAN_DEPENDENCY_DOWNGRADE=true \
  SCAN_SEMGREP=true \
  MODE=full \
  SCOPE=all \
  CODEQL_TRIGGER=all_codeql \
  CODEQL_LANGUAGE=auto \
  CODEQL_BUILD_MODE=none \
  CODEQL_TIMEOUT_SECONDS=14400 \
  FORCE_RESCAN=false \
  WORKER_IDLE_SECONDS=20
