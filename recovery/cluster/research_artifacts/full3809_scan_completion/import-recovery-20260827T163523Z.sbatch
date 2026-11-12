#!/bin/bash
#SBATCH --job-name=full3809-import
#SBATCH --partition=batch
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/full3809-final-import-%j.out
#SBATCH --error=/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/logs/full3809-final-import-%j.err

cd "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart" || true
source .venv/bin/activate 2>/dev/null || true

export PYTHONPATH="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1
export CONFIG="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/config.agentic_js.yml"
export DISTRIBUTED_SPOOL_ROOT="/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/distributed_spool"

python3 - <<'PY'
from pathlib import Path

from src.db.database import Database
from src.distributed.spool import DistributedSpool
from src.distributed import cheap_pipeline as cheap

db_path = Path(
    "/home-mscluster/astrauss/new/"
    "malicious-issue-miner-rate-smart/data/"
    "miner.agentic-js.eval.20260720_224159."
    "full3809-continuation.db"
)

spool_root = Path(
    "/home-mscluster/astrauss/new/"
    "malicious-issue-miner-rate-smart/data/"
    "distributed_spool"
)

db = Database(
    db_path,
    read_only=False,
    command_spool=None,
)

spool = DistributedSpool(spool_root)

cheap.ensure_import_table(db)

print("BEFORE =", spool.counts("cheap_analysis"), flush=True)

imported = cheap.import_results(
    db,
    spool,
)

print("IMPORTED =", imported, flush=True)
print("AFTER =", spool.counts("cheap_analysis"), flush=True)

print()
print("CHEAP JOB STATUS")

for jt in (
    "semgrep_source",
    "secret_ci",
    "dependency_downgrade",
    "osv_dependency",
    "trivy_dependency",
):
    rows = db.query(
        """
        SELECT status, COUNT(*) AS n
        FROM scanner_jobs
        WHERE job_type=?
        GROUP BY status
        ORDER BY status
        """,
        (jt,),
    )

    print(
        jt,
        [(row["status"], row["n"]) for row in rows],
        flush=True,
    )

runs = db.one(
    "SELECT COUNT(*) AS n FROM scanner_runs"
)

findings = db.one(
    "SELECT COUNT(*) AS n FROM scanner_findings"
)

print()
print("scanner_runs =", runs["n"], flush=True)
print("scanner_findings =", findings["n"], flush=True)
print("FINAL_IMPORT_STATUS=PASS", flush=True)
PY

RC=$?

echo "IMPORT_RC=$RC"
