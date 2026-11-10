#!/bin/bash
#SBATCH --job-name=ql3581_v2
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_forensics_v2/result.txt
#SBATCH --error=/home-mscluster/astrauss/research_artifacts/counterfactual_replay_r1/codeql_3581_forensics_v2/error.txt

set -euo pipefail

MINER="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
cd "$MINER"

[ -f .venv/bin/activate ] && source .venv/bin/activate
export PYTHONPATH="$MINER"

python3 - <<'PY'
import json
import sqlite3
from pathlib import Path

CASE = 3581
JOB = 600723

print("=== 1. ORIGINAL JOB ARTIFACT ===")

artifact = Path(
    "data/distributed_spool/codeql_security/results/imported/"
    "scanner-job-600723.json"
)

x = json.loads(artifact.read_text())

print("worker_id =", x.get("worker_id"))
print("slurm_job_id =", x.get("slurm_job_id"))
print("finished_at =", x.get("finished_at"))
print("task =", x.get("task"))

r = x.get("result", {})
print("status =", r.get("status"))
print("job_id =", r.get("job_id"))
print("case_id =", r.get("case_id"))

print("\nfindings:")
for f in r.get("findings", []):
    print(
        f.get("rule_id"),
        f.get("file_path"),
        f.get("line"),
        "introduced=", f.get("introduced")
    )

print("\n=== 2. ALL CODEQL JOBS FOR CASE 3581 ===")

db = Path(
    "data/final-study-snapshot-20260829/"
    "full3809-scanner-complete-20260829.db"
)

con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

for table in ("scanner_jobs", "scanner_runs", "scanner_findings"):
    cols = {
        row["name"]
        for row in con.execute(f"pragma table_info({table})")
    }

    print("\nTABLE", table)

    if "case_id" not in cols:
        print("no case_id")
        continue

    rows = con.execute(
        f"select * from {table} where case_id=?",
        (CASE,)
    ).fetchall()

    print("rows =", len(rows))

    for row in rows:
        d = dict(row)

        keep = {}
        for k in (
            "id", "job_id", "case_id", "job_type",
            "scanner", "rule_id", "file_path", "line",
            "introduced", "status", "attempts",
            "created_at", "started_at", "finished_at"
        ):
            if k in d:
                keep[k] = d[k]

        print(keep)

con.close()

print("\n=== 3. SAME WORKER'S OTHER RESULT ARTIFACTS ===")

worker = x.get("worker_id")
root = Path(
    "data/distributed_spool/codeql_security/results/imported"
)

same = []

for p in root.glob("*.json"):
    try:
        y = json.loads(p.read_text())
    except Exception:
        continue

    if y.get("worker_id") == worker:
        rr = y.get("result", {})
        same.append((
            y.get("finished_at"),
            p.name,
            rr.get("job_id"),
            rr.get("case_id"),
            len(rr.get("findings", []))
        ))

same.sort(key=lambda z: str(z[0]))

for row in same:
    print(row)

print("same_worker_artifacts =", len(same))

print("\n=== 4. SCANNER CLEANUP / INSERT LOGIC ===")

paths = [
    Path("src/scanners/codeql_scanner.py"),
    Path("src/distributed/codeql_pipeline.py"),
]

needles = (
    "DELETE FROM scanner_findings",
    "DELETE FROM scanner_runs",
    "scanner_findings",
    "scanner_runs",
    "export_result",
    "run_scanner_job",
)

for p in paths:
    print("\nFILE", p)

    lines = p.read_text(errors="ignore").splitlines()

    hits = set()

    for i, line in enumerate(lines):
        if any(n.lower() in line.lower() for n in needles):
            for j in range(max(0, i-4), min(len(lines), i+8)):
                hits.add(j)

    for j in sorted(hits):
        print(f"{j+1}: {lines[j]}")

print("\n=== 5. ORIGINAL SNAPSHOT DB CASE 3581 ===")

snap = Path(
    "data/distributed_spool/snapshots/codeql-security.db"
)

print("snapshot_exists =", snap.exists())

if snap.exists():
    con = sqlite3.connect(snap)
    con.row_factory = sqlite3.Row

    for table in ("scanner_jobs", "scanner_runs", "scanner_findings"):
        exists = con.execute(
            "select 1 from sqlite_master "
            "where type='table' and name=?",
            (table,)
        ).fetchone()

        if not exists:
            print(table, "MISSING")
            continue

        cols = {
            row["name"]
            for row in con.execute(f"pragma table_info({table})")
        }

        if "case_id" not in cols:
            continue

        rows = con.execute(
            f"select * from {table} where case_id=?",
            (CASE,)
        ).fetchall()

        print(table, "rows =", len(rows))

        for row in rows:
            d = dict(row)
            print({
                k: d[k]
                for k in d
                if k in (
                    "id", "job_id", "case_id", "job_type",
                    "scanner", "rule_id", "file_path",
                    "line", "introduced", "status",
                    "attempts", "created_at",
                    "started_at", "finished_at"
                )
            })

    con.close()

print("\nSTATUS=DONE")
PY
