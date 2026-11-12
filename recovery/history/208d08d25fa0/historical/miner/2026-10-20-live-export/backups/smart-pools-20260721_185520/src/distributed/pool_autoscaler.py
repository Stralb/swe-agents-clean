from __future__ import annotations

import argparse
import math
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from src.distributed.spool import DistributedSpool, atomic_replace_json, read_json

ROOT = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart")

SPECS: dict[str, dict[str, Any]] = {
    "mining": {
        "job_name": "mim-mining-worker",
        "aliases": {"mim-mining-worker", "miner-mining"},
        "script": ROOT / "run_distributed_mining.slurm",
        "partitions": "stampede,bigbatch,biggpu,batch",
        "cpus": 2,
        "memory": "8G",
        "time": "23:50:00",
        "minimum": int(os.getenv("MINING_MIN_WORKERS", "1")),
        "maximum": int(os.getenv("MINING_MAX_WORKERS", "4")),
        "tasks_per_worker": int(os.getenv("MINING_TASKS_PER_WORKER", "1")),
    },
    "cheap_analysis": {
        "job_name": "mim-cheap-worker",
        "aliases": {"mim-cheap-worker", "miner-dist-cheap"},
        "script": ROOT / "run_distributed_cheap.slurm",
        "partitions": "bigbatch,biggpu,stampede,batch",
        "cpus": 4,
        "memory": "32G",
        "time": "2-23:50:00",
        "minimum": int(os.getenv("CHEAP_MIN_WORKERS", "0")),
        "maximum": int(os.getenv("CHEAP_MAX_WORKERS", "8")),
        "tasks_per_worker": int(os.getenv("CHEAP_TASKS_PER_WORKER", "150")),
    },
    "codeql_security": {
        "job_name": "mim-codeql-worker",
        "aliases": {"mim-codeql-worker", "miner-dist-codeql"},
        "script": ROOT / "run_distributed_codeql.slurm",
        "partitions": "bigbatch,biggpu,stampede,batch",
        "cpus": 4,
        "memory": "64G",
        "time": "2-23:50:00",
        "minimum": int(os.getenv("CODEQL_MIN_WORKERS", "0")),
        "maximum": int(os.getenv("CODEQL_MAX_WORKERS", "8")),
        "tasks_per_worker": int(os.getenv("CODEQL_TASKS_PER_WORKER", "20")),
    },
}

ACTIVE_STATES = {"PENDING", "CONFIGURING", "RUNNING", "COMPLETING"}


def spool_root() -> Path:
    return Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(ROOT / "data/distributed_spool"),
        )
    )


def _jobs() -> list[dict[str, str]]:
    result = subprocess.run(
        ["squeue", "-u", os.getenv("USER", ""), "-h", "-o", "%i|%j|%T"],
        capture_output=True,
        text=True,
        check=False,
    )
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.strip().split("|", 2)
        if len(parts) != 3:
            continue
        rows.append({"job_id": parts[0], "name": parts[1], "state": parts[2].upper()})
    return rows


def _fresh_heartbeats(spool: DistributedSpool, pool: str) -> list[dict[str, Any]]:
    now = time.time()
    rows: list[dict[str, Any]] = []
    for path in spool.queue_path(pool, "heartbeats").glob("*.json"):
        try:
            row = read_json(path)
        except Exception:
            continue
        updated = float(row.get("updated_at") or path.stat().st_mtime)
        if now - updated <= 180:
            rows.append(row)
    return rows


def _desired(spec: dict[str, Any], counts: dict[str, int]) -> int:
    pending = int(counts.get("pending", 0))
    claimed = int(counts.get("claimed", 0))
    extra = math.ceil(pending / max(1, int(spec["tasks_per_worker"])))
    return max(
        int(spec["minimum"]),
        min(int(spec["maximum"]), claimed + extra),
    )


def _submit(pool: str, spec: dict[str, Any], dry_run: bool) -> str:
    script = Path(spec["script"])
    if not script.exists():
        raise RuntimeError(f"Missing worker script: {script}")

    command = [
        "sbatch",
        "--parsable",
        f"--job-name={spec['job_name']}",
        f"--partition={spec['partitions']}",
        f"--time={spec['time']}",
        f"--cpus-per-task={spec['cpus']}",
        f"--mem={spec['memory']}",
        "--signal=B:TERM@300",
        f"--output={ROOT}/logs/{spec['job_name']}-%j.out",
        f"--error={ROOT}/logs/{spec['job_name']}-%j.err",
        "--export=ALL,DISTRIBUTED_SPOOL_ROOT=" + str(spool_root()) + ",CONFIG=" + str(ROOT / "config.agentic_js.yml"),
        str(script),
    ]

    if dry_run:
        return "DRY_RUN:" + " ".join(command)

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "sbatch failed")
    return result.stdout.strip().split(";")[0]


def _cancel(job_id: str, dry_run: bool) -> None:
    if dry_run:
        return
    subprocess.run(["scancel", job_id], check=False)


def run_once(*, dry_run: bool) -> dict[str, Any]:
    spool = DistributedSpool(spool_root())
    jobs = _jobs()
    status: dict[str, Any] = {
        "updated_at": time.time(),
        "dry_run": dry_run,
        "pools": {},
    }

    for pool, spec in SPECS.items():
        counts = spool.counts(pool)
        active = [
            job
            for job in jobs
            if job["name"] in spec["aliases"] and job["state"] in ACTIVE_STATES
        ]
        managed = [job for job in active if job["name"] == spec["job_name"]]
        desired = _desired(spec, counts)
        submitted: list[str] = []
        cancelled: list[str] = []
        errors: list[str] = []

        if len(active) < desired:
            for _ in range(desired - len(active)):
                try:
                    submitted.append(_submit(pool, spec, dry_run))
                except Exception as exc:
                    errors.append(str(exc))

        elif len(active) > desired and int(counts.get("pending", 0)) == 0:
            heartbeats = _fresh_heartbeats(spool, pool)
            working_job_ids = {
                str(row.get("slurm_job_id") or "")
                for row in heartbeats
                if str(row.get("state") or "").lower() == "working"
            }
            removable = [
                job
                for job in managed
                if job["job_id"].split("_", 1)[0] not in working_job_ids
            ]
            for job in removable[: max(0, len(active) - desired)]:
                _cancel(job["job_id"], dry_run)
                cancelled.append(job["job_id"])

        decision = "steady"
        if submitted:
            decision = "scale_up"
        elif cancelled:
            decision = "scale_down"
        elif len(active) < desired and errors:
            decision = "scale_up_failed"

        status["pools"][pool] = {
            "counts": counts,
            "active_workers": len(active),
            "desired_workers": desired,
            "fresh_heartbeats": len(_fresh_heartbeats(spool, pool)),
            "decision": decision,
            "submitted": submitted,
            "cancelled": cancelled,
            "errors": errors,
        }

    atomic_replace_json(spool.root / "status" / "autoscaler.json", status)
    print(status, flush=True)
    return status


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    while True:
        run_once(dry_run=args.dry_run)
        if args.once:
            return
        time.sleep(max(10, args.interval))


if __name__ == "__main__":
    main()
