#!/bin/bash
#SBATCH --job-name=ql_db3581
#SBATCH --partition=batch
#SBATCH --time=00:05:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_db_forensics/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_db_forensics/error.txt

set -euo pipefail

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$MINER"

export PYTHONPATH="$MINER"

python3 - <<'PY'
import sqlite3
import inspect
from pathlib import Path
import src.distributed.codeql_pipeline as cp

dbs = [
    Path("data/distributed_spool/snapshots/codeql-security.db"),
    Path("data/final-study-snapshot-20260829/full3809-scanner-complete-20260829.db"),
]

def dump_table(con, table):
    exists = con.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (table,)
    ).fetchone()

    if not exists:
        print(table, "MISSING")
        return

    cols = [r[1] for r in con.execute(f"pragma table_info({table})")]
    print("\nTABLE", table)
    print("COLUMNS", cols)

    if "case_id" in cols:
        rows = con.execute(
            f"select * from {table} where case_id=3581"
        ).fetchall()
    elif table == "scanner_jobs":
        rows = con.execute(
            "select * from scanner_jobs where id=600723 or case_id=3581"
        ).fetchall()
    else:
        rows = []

    print("ROWS", len(rows))
    for r in rows:
        print(dict(zip(cols, r)))

for db in dbs:
    print("\n================================================")
    print("DATABASE", db)
    print("exists=", db.exists())

    if not db.exists():
        continue

    con = sqlite3.connect(db)

    for table in ("scanner_jobs", "scanner_runs", "scanner_findings"):
        dump_table(con, table)

    con.close()

print("\n================================================")
print("EXPORT_RESULT SOURCE")
print(inspect.getsource(cp.export_result))

print("\n================================================")
print("RUN_SCANNER_JOB SOURCE")
if hasattr(cp, "run_scanner_job"):
    print(inspect.getsource(cp.run_scanner_job))
else:
    print("run_scanner_job not directly exposed")

print("\n================================================")
print("DELETE/CLEAR LOGIC")

for p in Path("src").rglob("*.py"):
    txt = p.read_text(errors="ignore")
    for i, line in enumerate(txt.splitlines(), 1):
        low = line.lower()
        if (
            ("delete" in low or "clear" in low)
            and ("scanner_find" in low or "scanner_run" in low)
        ):
            print(f"{p}:{i}:{line.strip()}")

print("\nSTATUS=DONE")
PY
