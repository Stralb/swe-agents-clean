#!/bin/bash
#SBATCH --job-name=miner-native
#SBATCH --partition=biggpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --time=23:00:00
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/%u/miner_native_%j.log

set -euo pipefail

PROJECT=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart

echo "--- HOST ---"
hostname
echo "--- PROJECT ---"
cd "$PROJECT"
pwd

echo "--- LOAD TOKEN ---"
source "$PROJECT/.env.cluster"

echo "--- ACTIVATE VENV ---"
source "$PROJECT/.venv/bin/activate"

echo "--- PATHS ---"
export PATH="/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$HOME/.local/bin:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export DB_PATH=data/miner.db

export MINER_CODEQL_TMPDIR="/tmp/$USER/miner-codeql-tmp"
export CODEQL_TMPDIR="/tmp/$USER/miner-codeql-tmp"
export CODEQL_RAM_MB=24576
export CODEQL_THREADS=4

mkdir -p "$MINER_CODEQL_TMPDIR"
mkdir -p logs

echo "--- TOOL CHECK ---"
python --version
git --version
make --version | head -n 1
which codeql
codeql version

echo "--- DB BEFORE ---"
python scripts/status.py || true

echo "--- CODEQL PACK CHECK ---"
which codeql
codeql version
codeql pack download codeql/javascript-queries
codeql pack download codeql/python-queries
codeql resolve packs | grep -E "javascript-queries|python-queries" || true
codeql resolve queries codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls | head -n 20

echo "--- RUNNING CODEQL SCAN ---"
make scan \
  MODE=full \
  MAX_CASES=500 \
  CODEQL_TRIGGER=all_codeql \
  CODEQL_LANGUAGE=auto \
  CODEQL_QUERY_SUITE="codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls" \
  CODEQL_MAX_PER_RUN=20 \
  CODEQL_WORKERS=1 \
  CODEQL_BUILD_MODE=none \
  CODEQL_TIMEOUT_SECONDS=14400 \
  SCAN_CODEQL=true \
  SCAN_GITLEAKS=false \
  SCAN_OSV=false \
  SCAN_DEPENDENCY_DOWNGRADE=false \
  FORCE_RESCAN=false

echo "--- DB AFTER ---"
python scripts/status.py || true

echo "--- DONE ---"
