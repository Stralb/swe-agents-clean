#!/bin/bash
#SBATCH --job-name=serial-all-eval
#SBATCH --partition=biggpu
#SBATCH --time=1-00:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --output=/home-mscluster/%u/serial_all_eval_%j.log

set -euo pipefail

PROJECT=/home-mscluster/$USER/new/malicious-issue-miner-rate-smart
cd "$PROJECT"

source "$PROJECT/.env.cluster"
source "$PROJECT/.venv/bin/activate"

export PATH="/home-mscluster/$USER/tools/bin:/home-mscluster/$USER/tools/node/bin:/home-mscluster/$USER/tools/codeql:$PATH"
export PYTHONPATH=.
export CONFIG=config.yml
export PYTHON=./.venv/bin/python

export EVAL_TMP_DIR="/tmp/$USER/malicious-eval-$SLURM_JOB_ID"
export DB_PATH="$EVAL_TMP_DIR/miner.eval.db"
mkdir -p "$EVAL_TMP_DIR"

cp "$PROJECT/data/miner.eval.input.db" "$DB_PATH"

export MINER_WORKER_ID="serial-all-eval-$SLURM_JOB_ID"
export MINER_CODEQL_TMPDIR="/tmp/$USER/codeql-$SLURM_JOB_ID"
export CODEQL_TMPDIR="$MINER_CODEQL_TMPDIR"
mkdir -p "$MINER_CODEQL_TMPDIR"

export CODEQL_RAM_MB=20000
export CODEQL_THREADS=4

echo "JOB=$SLURM_JOB_ID"
echo "NODE=$(hostname)"
echo "DB_PATH=$DB_PATH"
ls -lh "$DB_PATH"

./.venv/bin/python - <<'PY'
import os
import sqlite3
import yaml
from pathlib import Path
from types import SimpleNamespace

from src.db.database import Database
from src.workers import job_queue

db = Database(Path(os.environ["DB_PATH"]))

with open(os.environ.get("CONFIG", "config.yml"), "r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

settings = SimpleNamespace(config=config)

# Serial evaluator mode:
# no supervisor, no heartbeat loop, no threaded SQLite storm.
job_queue.update_case_stages = lambda db: None

def status_pair(db, case_id, job_type):
    status = job_queue._job_status_from_runs(db, case_id, job_type)
    if not status:
        status = "error"
        detail = "scanner produced no recognized scanner_run"
    else:
        detail = status
    return status, detail

job_queue._job_status_from_scanner_runs = status_pair

def print_state(label):
    with sqlite3.connect(os.environ["DB_PATH"]) as con:
        cur = con.cursor()
        print(f"\n================ {label} ================", flush=True)

        print("SCANNER JOBS", flush=True)
        for r in cur.execute("""
        SELECT job_type, status, COUNT(*)
        FROM scanner_jobs
        GROUP BY job_type, status
        ORDER BY job_type, status
        """):
            print(tuple(r), flush=True)

        print("\nRUNS", flush=True)
        for r in cur.execute("""
        SELECT scanner, status, COUNT(*)
        FROM scanner_runs
        GROUP BY scanner, status
        ORDER BY scanner, status
        """):
            print(tuple(r), flush=True)

        print("\nFINDINGS", flush=True)
        for r in cur.execute("""
        SELECT scanner, finding_type, introduced, COUNT(*)
        FROM scanner_findings
        GROUP BY scanner, finding_type, introduced
        ORDER BY COUNT(*) DESC
        """):
            print(tuple(r), flush=True)

print_state("START")

lanes = [
    ("dependency", ["dependency_downgrade", "osv_dependency"]),
    ("secret", ["secret_ci"]),
    ("codeql", ["codeql"]),
]

for lane_name, job_types in lanes:
    worker_id = f"serial-{lane_name}-{os.environ.get('SLURM_JOB_ID', 'local')}"
    done = 0
    print(f"\n================ LANE {lane_name} job_types={job_types} ================", flush=True)

    while True:
        job = job_queue.claim_job(db, job_types, worker_id=worker_id)
        if job is None:
            print(f"NO_MORE_JOBS lane={lane_name} done={done}", flush=True)
            break

        print(f"RUN lane={lane_name} job_id={job.id} case_id={job.case_id} job_type={job.job_type}", flush=True)
        job_queue.run_scanner_job(db, settings, job)
        done += 1

    print_state(f"AFTER {lane_name}")

print_state("FINAL")
PY

echo
echo "================ COPY DB BACK ================"
cp "$DB_PATH" "$PROJECT/data/miner.eval.output.${SLURM_JOB_ID}.db"
cp "$PROJECT/data/miner.db" "$PROJECT/data/miner.before_serial_all_eval_${SLURM_JOB_ID}.db"
cp "$DB_PATH" "$PROJECT/data/miner.db"

ls -lh "$PROJECT/data/miner.db" "$PROJECT/data/miner.eval.output.${SLURM_JOB_ID}.db"
echo "DONE serial all evaluator"
