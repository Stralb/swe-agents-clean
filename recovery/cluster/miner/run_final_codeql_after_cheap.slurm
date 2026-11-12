#!/bin/bash
#SBATCH --job-name=final-codeql
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:309
#SBATCH --time=14:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=56G
#SBATCH --output=/home-mscluster/%u/final_codeql_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster

if [ ! -f .final_cheap_done_db ]; then
  echo "ERROR: .final_cheap_done_db missing"
  exit 2
fi

source .final_cheap_done_db

ORIGINAL_DB="$DB_PATH"
LOCAL_DB="/tmp/$USER/final-codeql-$SLURM_JOB_ID.db"
RESULT_DB="${ORIGINAL_DB%.db}.codeql_done.db"

mkdir -p "/tmp/$USER"

cp "$ORIGINAL_DB" "$LOCAL_DB"

export DB_PATH="$LOCAL_DB"
export PYTHONPATH=.
export CONFIG=config.yml
export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/go/bin:/home-mscluster/$USER/tools/codeql:$PATH"

export CODEQL_TMPDIR="/tmp/$USER/codeql-final-$SLURM_JOB_ID"
export MINER_CODEQL_TMPDIR="$CODEQL_TMPDIR"
export CODEQL_RAM_MB=42000
export CODEQL_THREADS=2

mkdir -p "$CODEQL_TMPDIR"

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "ORIGINAL_DB=$ORIGINAL_DB"
echo "LOCAL_DB=$LOCAL_DB"
echo "RESULT_DB=$RESULT_DB"
echo "START=$(date)"

which codeql
codeql version

echo "===== ENSURE PACKS ====="
codeql pack download codeql/python-queries || true
codeql pack download codeql/javascript-queries || true
codeql pack download codeql/go-queries || true
codeql pack download codeql/ruby-queries || true
codeql pack download codeql/java-queries || true
codeql pack download codeql/cpp-queries || true
codeql pack download codeql/csharp-queries || true

./.venv/bin/python - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB_PATH"])
cur = con.cursor()

cur.execute("""
UPDATE scanner_jobs
SET status='pending',
    attempts=0,
    started_at=NULL,
    finished_at=NULL,
    worker_id=NULL,
    last_error=NULL
WHERE job_type='codeql'
  AND status IN ('running','error')
""")

con.commit()

print("CODEQL BEFORE")
for r in cur.execute("""
SELECT status, COUNT(*)
FROM scanner_jobs
WHERE job_type='codeql'
GROUP BY status
ORDER BY status
"""):
    print(r)

con.close()
PY

echo "===== RUN FINAL CODEQL ====="
make evaluate-codeql

echo "===== POST CODEQL STATUS ====="
make methodology-profile
make methodology-status
make region-yield

cp "$LOCAL_DB" "$RESULT_DB"
echo "export DB_PATH=\"$RESULT_DB\"" > .final_codeql_done_db

echo "COPIED RESULT TO $RESULT_DB"
echo "END=$(date)"
