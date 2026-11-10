#!/bin/bash
#SBATCH --job-name=codeql-after-cheap
#SBATCH --partition=biggpu
#SBATCH --dependency=afterok:280
#SBATCH --time=10:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=56G
#SBATCH --output=/home-mscluster/%u/codeql_after_cheap_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "START=$(date)"
echo "Dependency cheap job 280 completed OK"

if [ ! -f .snapshot_eval_cheap_done_db ]; then
  echo "ERROR: .snapshot_eval_cheap_done_db does not exist. Cheap eval probably failed before writing result pointer."
  exit 2
fi

source .snapshot_eval_cheap_done_db

ORIGINAL_DB="$DB_PATH"
LOCAL_DB="/tmp/$USER/eval-codeql-after-cheap-$SLURM_JOB_ID.db"
RESULT_DB="${ORIGINAL_DB%.db}.codeql_done.db"

mkdir -p "/tmp/$USER"

echo "ORIGINAL_DB=$ORIGINAL_DB"
echo "LOCAL_DB=$LOCAL_DB"
echo "RESULT_DB=$RESULT_DB"

if [ ! -f "$ORIGINAL_DB" ]; then
  echo "ERROR: cheap-done DB does not exist: $ORIGINAL_DB"
  exit 3
fi

cp "$ORIGINAL_DB" "$LOCAL_DB"

export DB_PATH="$LOCAL_DB"
export PYTHONPATH=.
export CONFIG=config.yml
export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/go/bin:/home-mscluster/$USER/tools/codeql:$PATH"

export CODEQL_TMPDIR="/tmp/$USER/codeql-after-cheap-$SLURM_JOB_ID"
export MINER_CODEQL_TMPDIR="$CODEQL_TMPDIR"
export CODEQL_RAM_MB=42000
export CODEQL_THREADS=2

mkdir -p "$CODEQL_TMPDIR"

echo "===== TOOL CHECK ====="
which codeql
codeql version
which go || true
which node || true

echo "===== INSTALL/VERIFY CODEQL PACKS ====="
codeql pack download codeql/python-queries || true
codeql pack download codeql/javascript-queries || true
codeql pack download codeql/go-queries || true
codeql pack download codeql/ruby-queries || true
codeql pack download codeql/java-queries || true
codeql pack download codeql/cpp-queries || true
codeql pack download codeql/csharp-queries || true

codeql resolve packs | grep -E "codeql/(python|javascript|go|ruby|java|cpp|csharp)-queries" || true

echo "===== RESET CODEQL ERRORS/RUNNING ONLY IN LOCAL COPY ====="
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

print("CODEQL JOBS BEFORE")
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

echo "===== RUN CODEQL EVAL ON LOCAL TMP DB ====="
make evaluate-codeql

echo "===== POST CODEQL STATUS ====="
make methodology-profile
make methodology-status
make region-yield

cp "$LOCAL_DB" "$RESULT_DB"
echo "export DB_PATH=\"$RESULT_DB\"" > .snapshot_eval_codeql_done_db

echo "COPIED RESULT TO $RESULT_DB"
echo "END=$(date)"
