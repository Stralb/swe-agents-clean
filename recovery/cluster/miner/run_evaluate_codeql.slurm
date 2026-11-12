#!/bin/bash
#SBATCH --job-name=miner-evaluate-codeql
#SBATCH --partition=biggpu
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/%u/miner_evaluate-codeql_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart
source .venv/bin/activate
if [ -f .env.cluster ]; then source .env.cluster; fi
export PYTHONPATH=.
export CONFIG=${CONFIG:-config.yml}
export DB_PATH=${DB_PATH:-$PWD/data/miner.db}
export PATH="/home-mscluster/$USER/tools/go/bin:/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"
export CODEQL_TMPDIR=${CODEQL_TMPDIR:-/tmp/$USER/codeql-$SLURM_JOB_ID}
export MINER_CODEQL_TMPDIR="$CODEQL_TMPDIR"
export GOCACHE=${GOCACHE:-/tmp/$USER/go-cache-$SLURM_JOB_ID}
export GOMODCACHE=${GOMODCACHE:-/tmp/$USER/go-modcache-$SLURM_JOB_ID}
mkdir -p "$CODEQL_TMPDIR" "$GOCACHE" "$GOMODCACHE"
echo "JOB=$SLURM_JOB_ID NODE=$(hostname) DB=$DB_PATH"


codeql pack download codeql/go-queries || true
export CODEQL_RAM_MB=${CODEQL_RAM_MB:-48000}
export CODEQL_THREADS=${CODEQL_THREADS:-2}
make evaluate-codeql
make methodology-profile
make methodology-status

