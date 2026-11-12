#!/bin/bash
#SBATCH --job-name=go-codeql-rerun
#SBATCH --partition=biggpu
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --output=/home-mscluster/%u/go_codeql_rerun_%j.log

set -euo pipefail

cd /home-mscluster/$USER/new/malicious-issue-miner-rate-smart

source .venv/bin/activate
source .env.cluster

export DB_PATH="$PWD/data/miner.eval.rerun.db"
export PYTHONPATH=.
export CONFIG=config.yml
export PYTHON=./.venv/bin/python

export PATH="/home-mscluster/$USER/tools/go/bin:/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"

export MINER_CODEQL_TMPDIR="/tmp/$USER/codeql-go-rerun-$SLURM_JOB_ID"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"
export CODEQL_RAM_MB=20000
export CODEQL_THREADS=4

mkdir -p "$MINER_CODEQL_TMPDIR"

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "DB_PATH=$DB_PATH"
which go
go version
which codeql
codeql version

echo "===== START STATUS ====="
./.venv/bin/python - <<'PY'
import sqlite3, os
con = sqlite3.connect(os.environ["DB_PATH"])
cur = con.cursor()
for r in cur.execute("""
SELECT job_type,status,COUNT(*)
FROM scanner_jobs
GROUP BY job_type,status
ORDER BY job_type,status
"""):
    print(r)
con.close()
PY

echo "===== RUN GO CODEQL CASES ====="
./.venv/bin/python - <<'PY'
import os
import yaml
from pathlib import Path
from types import SimpleNamespace

from src.db.database import Database
from src.workers import job_queue

db = Database(Path(os.environ["DB_PATH"]))

with open(os.environ.get("CONFIG", "config.yml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

settings = SimpleNamespace(config=config)

# Avoid supervisor/status refresh storm.
job_queue.update_case_stages = lambda db: None

def status_pair(db, case_id, job_type):
    status = job_queue._job_status_from_runs(db, case_id, job_type)
    if not status:
        status = "error"
    return status, status

job_queue._job_status_from_scanner_runs = status_pair

go_cases = {22,23,24,25,26,27,28,39}
done = 0

while True:
    job = job_queue.claim_job(db, ["codeql"], worker_id=f"go-codeql-slurm-{os.environ.get('SLURM_JOB_ID','unknown')}")
    if job is None:
        print("NO_MORE_CODEQL_JOBS", flush=True)
        break

    if job.case_id not in go_cases:
        with db.connect() as con:
            con.execute(
                "UPDATE scanner_jobs SET status='pending', started_at=NULL, worker_id=NULL WHERE id=?",
                (job.id,),
            )
            con.commit()
        print(f"STOP non-target job_id={job.id} case_id={job.case_id}", flush=True)
        break

    print(f"RUN_GO_CODEQL job_id={job.id} case_id={job.case_id}", flush=True)
    job_queue.run_scanner_job(db, settings, job)
    done += 1

print(f"GO_CODEQL_SLURM_DONE jobs={done}", flush=True)
PY

echo "===== FINAL STATUS ====="
./.venv/bin/python - <<'PY'
import sqlite3, os
con = sqlite3.connect(os.environ["DB_PATH"])
cur = con.cursor()

print("\nSCANNER JOBS")
for r in cur.execute("""
SELECT job_type,status,COUNT(*)
FROM scanner_jobs
GROUP BY job_type,status
ORDER BY job_type,status
"""):
    print(r)

print("\nGO CASE STATUS")
for r in cur.execute("""
SELECT case_id,status,attempts,started_at,finished_at,last_error
FROM scanner_jobs
WHERE job_type='codeql'
  AND case_id IN (22,23,24,25,26,27,28,39)
ORDER BY case_id
"""):
    print(r)

print("\nFINDINGS")
for r in cur.execute("""
SELECT scanner,finding_type,introduced,COUNT(*)
FROM scanner_findings
GROUP BY scanner,finding_type,introduced
ORDER BY COUNT(*) DESC
"""):
    print(r)

print("\nGO CODEQL RUN SUMMARY")
for r in cur.execute("""
SELECT case_id, scanner, status, COUNT(*)
FROM scanner_runs
WHERE case_id IN (22,23,24,25,26,27,28,39)
  AND lower(scanner) LIKE '%codeql%'
GROUP BY case_id, scanner, status
ORDER BY case_id, scanner, status
"""):
    print(r)

con.close()
PY
