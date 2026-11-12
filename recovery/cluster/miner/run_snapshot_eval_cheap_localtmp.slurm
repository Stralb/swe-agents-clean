#!/bin/bash
#SBATCH --job-name=eval-cheap-tmp
#SBATCH --partition=biggpu
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=24G
#SBATCH --output=/home-mscluster/%u/eval_cheap_localtmp_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster
source .snapshot_eval_localtmp_db

ORIGINAL_DB="$DB_PATH"
LOCAL_DB="/tmp/$USER/eval-cheap-$SLURM_JOB_ID.db"
RESULT_DB="${ORIGINAL_DB%.db}.cheap_done.db"

mkdir -p "/tmp/$USER"

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "ORIGINAL_DB=$ORIGINAL_DB"
echo "LOCAL_DB=$LOCAL_DB"
echo "RESULT_DB=$RESULT_DB"

cp "$ORIGINAL_DB" "$LOCAL_DB"

export DB_PATH="$LOCAL_DB"
export PYTHONPATH=.
export CONFIG=config.yml

# Reset stale running jobs inside local copy only.
./.venv/bin/python - <<'PY'
import os, sqlite3
con = sqlite3.connect(os.environ["DB_PATH"])
cur = con.cursor()
cur.execute("""
UPDATE scanner_jobs
SET status='pending',
    started_at=NULL,
    finished_at=NULL,
    worker_id=NULL,
    last_error=NULL
WHERE status='running'
""")
con.commit()
print("quick_check", cur.execute("PRAGMA quick_check").fetchone())
for r in cur.execute("""
SELECT job_type,status,COUNT(*)
FROM scanner_jobs
GROUP BY job_type,status
ORDER BY job_type,status
"""):
    print(r)
con.close()
PY

echo "===== RUN CHEAP EVAL ON LOCAL TMP DB ====="
make evaluate-cheap

echo "===== POST CHEAP STATUS ====="
make methodology-profile
make methodology-status
make region-yield

cp "$LOCAL_DB" "$RESULT_DB"
echo "export DB_PATH=\"$RESULT_DB\"" > .snapshot_eval_cheap_done_db

echo "COPIED RESULT TO $RESULT_DB"
