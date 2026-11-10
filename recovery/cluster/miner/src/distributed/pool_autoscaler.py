from __future__ import annotations

import argparse
import math
import os
import subprocess
import time
from collections import Counter
from pathlib import Path
from typing import Any

from src.distributed.pool_control import (
    PARTITION_LIMITS,
    load_pool_policy,
    pool_enabled,
)
from src.distributed.pipeline_scheduler import compute_targets
from src.distributed.spool import (
    DistributedSpool,
    atomic_replace_json,
    read_json,
)

ROOT = Path(
    "/home-mscluster/astrauss/new/"
    "malicious-issue-miner-rate-smart"
)

ACTIVE_STATES = {
    "PENDING",
    "CONFIGURING",
    "RUNNING",
    "COMPLETING",
}

SPECS: dict[str, dict[str, Any]] = {
    "codeql_security": {
        "job_name": "mim-codeql-worker",
        "aliases": {
            "mim-codeql-worker",
            "miner-dist-codeql",
        },
        "script": ROOT / "run_distributed_codeql.slurm",
        "cpus": 4,
        "memory": "64G",
        "time": "2-23:50:00",
        "tasks_per_worker": 20,
        "allowed_partitions": {
            "biggpu",
            "bigbatch",
        },
    },
    "cheap_analysis": {
        "job_name": "mim-cheap-worker",
        "aliases": {
            "mim-cheap-worker",
            "miner-dist-cheap",
        },
        "script": ROOT / "run_distributed_cheap.slurm",
        "cpus": 4,
        "memory": "32G",
        "time": "2-23:50:00",
        "tasks_per_worker": 150,
        "allowed_partitions": {
            "bigbatch",
            "biggpu",
        },
    },
    "mining": {
        "job_name": "mim-mining-worker",
        "aliases": {
            "mim-mining-worker",
            "miner-mining",
        },
        "script": ROOT / "run_distributed_mining.slurm",
        "cpus": 2,
        "memory": "8G",
        "time": "23:50:00",
        "tasks_per_worker": 1,
        "allowed_partitions": {
            "stampede",
            "bigbatch",
            "batch",
            "biggpu",
        },
    },
}


def spool_root() -> Path:
    return Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(ROOT / "data/distributed_spool"),
        )
    )


def _jobs() -> list[dict[str, str]]:
    result = subprocess.run(
        [
            "squeue",
            "-u",
            os.getenv("USER", ""),
            "-h",
            "-o",
            "%i|%j|%T|%P",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    rows: list[dict[str, str]] = []

    for line in result.stdout.splitlines():
        parts = line.strip().split("|", 3)

        if len(parts) != 4:
            continue

        rows.append(
            {
                "job_id": parts[0],
                "name": parts[1],
                "state": parts[2].upper(),
                "partition": parts[3],
            }
        )

    return rows


def _active_job_ids(
    jobs: list[dict[str, str]],
) -> set[str]:
    identifiers: set[str] = set()

    for job in jobs:
        job_id = str(job["job_id"])
        identifiers.add(job_id)
        identifiers.add(
            job_id.split("_", 1)[0]
        )

    return identifiers


def _partition_capacity() -> dict[str, dict[str, int]]:
    status: dict[str, dict[str, int]] = {}

    for partition in PARTITION_LIMITS:
        result = subprocess.run(
            [
                "sinfo",
                "-h",
                "-p",
                partition,
                "-o",
                "%a|%t|%D",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        idle_nodes = 0
        usable_nodes = 0
        total_nodes = 0

        for line in result.stdout.splitlines():
            parts = line.strip().split("|", 2)

            if len(parts) != 3:
                continue

            availability = parts[0].lower()
            state = parts[1].lower().rstrip("*")

            try:
                nodes = int(parts[2])
            except ValueError:
                continue

            total_nodes += nodes

            if availability != "up":
                continue

            if state.startswith("idle"):
                idle_nodes += nodes
                usable_nodes += nodes
            elif (
                state.startswith("mix")
                or state.startswith("alloc")
            ):
                usable_nodes += nodes

        status[partition] = {
            "idle_nodes": idle_nodes,
            "usable_nodes": usable_nodes,
            "total_nodes": total_nodes,
        }

    return status


def _active_for_pool(
    jobs: list[dict[str, str]],
    pool: str,
) -> list[dict[str, str]]:
    aliases = SPECS[pool]["aliases"]

    return [
        job
        for job in jobs
        if job["name"] in aliases
        and job["state"] in ACTIVE_STATES
    ]


def _pool_preferences(
    policy: dict[str, Any],
    pool: str,
) -> list[str]:
    pool_policy = policy["pools"][pool]
    allowed = SPECS[pool]["allowed_partitions"]

    return [
        partition
        for partition in pool_policy[
            "partition_preferences"
        ]
        if partition in allowed
    ]


def _desired_workers(
    policy: dict[str, Any],
    pool: str,
    counts: dict[str, int],
) -> int:
    if not pool_enabled(policy, pool):
        return 0

    pending = int(
        counts.get("pending", 0)
    )

    claimed = int(
        counts.get("claimed", 0)
    )

    tasks_per_worker = max(
        1,
        int(
            SPECS[pool]["tasks_per_worker"]
        ),
    )

    maximum = max(
        0,
        int(
            policy["pools"][pool][
                "max_workers"
            ]
        ),
    )

    return min(
        maximum,
        claimed
        + math.ceil(
            pending / tasks_per_worker
        ),
    )


def _fresh_heartbeats(
    spool: DistributedSpool,
    pool: str,
) -> list[dict[str, Any]]:
    now = time.time()
    rows: list[dict[str, Any]] = []

    for path in spool.queue_path(
        pool,
        "heartbeats",
    ).glob("*.json"):
        try:
            row = read_json(path)
        except Exception:
            continue

        updated = float(
            row.get("updated_at")
            or path.stat().st_mtime
        )

        if now - updated <= 180:
            rows.append(row)

    return rows


def _heartbeat_by_job(
    spool: DistributedSpool,
    pool: str,
) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}

    for row in _fresh_heartbeats(
        spool,
        pool,
    ):
        job_id = str(
            row.get("slurm_job_id") or ""
        )

        if not job_id:
            continue

        previous = latest.get(job_id)

        if (
            previous is None
            or float(
                row.get("updated_at") or 0
            )
            > float(
                previous.get("updated_at") or 0
            )
        ):
            latest[job_id] = row

    return latest


def _requeue_orphaned_claims(
    spool: DistributedSpool,
    pool: str,
    active_ids: set[str],
) -> int:
    changed = 0
    claimed_directory = spool.queue_path(
        pool,
        "claimed",
    )
    heartbeat_directory = spool.queue_path(
        pool,
        "heartbeats",
    )
    pending_directory = spool.queue_path(
        pool,
        "pending",
    )
    result_directory = spool.queue_path(
        pool,
        "results",
    )

    for claimed in claimed_directory.glob(
        "*.json"
    ):
        stem = claimed.stem

        if "__" not in stem:
            continue

        task_id, worker_key = stem.split(
            "__",
            1,
        )

        heartbeat_path = (
            heartbeat_directory
            / f"{worker_key}.json"
        )

        if not heartbeat_path.exists():
            continue

        try:
            heartbeat = read_json(
                heartbeat_path
            )
        except Exception:
            continue

        job_id = str(
            heartbeat.get("slurm_job_id")
            or ""
        )

        if (
            job_id
            and job_id in active_ids
        ):
            continue

        result_path = (
            result_directory
            / f"{task_id}.json"
        )

        if result_path.exists():
            claimed.unlink(
                missing_ok=True
            )
            changed += 1
            continue

        pending_path = (
            pending_directory
            / f"{task_id}.json"
        )

        if pending_path.exists():
            claimed.unlink(
                missing_ok=True
            )
            changed += 1
            continue

        try:
            os.replace(
                claimed,
                pending_path,
            )
            changed += 1
        except FileNotFoundError:
            continue

    return changed


def _choose_partition(
    policy: dict[str, Any],
    pool: str,
    occupancy: Counter[str],
    capacity: dict[str, dict[str, int]],
) -> str | None:
    eligible: list[str] = []

    for partition in _pool_preferences(
        policy,
        pool,
    ):
        if (
            occupancy[partition]
            >= PARTITION_LIMITS[partition]
        ):
            continue

        if (
            capacity.get(
                partition,
                {},
            ).get("usable_nodes", 0)
            <= 0
        ):
            continue

        eligible.append(partition)

    if not eligible:
        return None

    immediately_available = [
        partition
        for partition in eligible
        if capacity.get(
            partition,
            {},
        ).get("idle_nodes", 0)
        > 0
    ]

    if immediately_available:
        return immediately_available[0]

    return eligible[0]


def _submit(
    pool: str,
    partition: str,
    *,
    dry_run: bool,
) -> str:
    spec = SPECS[pool]
    script = Path(spec["script"])

    if not script.exists():
        raise RuntimeError(
            f"Missing worker script: {script}"
        )

    command = [
        "sbatch",
        "--parsable",
        f"--job-name={spec['job_name']}",
        f"--partition={partition}",
        f"--time={spec['time']}",
        f"--cpus-per-task={spec['cpus']}",
        f"--mem={spec['memory']}",
        "--signal=B:TERM@300",
        (
            f"--output={ROOT}/logs/"
            f"{spec['job_name']}-%j.out"
        ),
        (
            f"--error={ROOT}/logs/"
            f"{spec['job_name']}-%j.err"
        ),
        (
            "--export=ALL,"
            f"DISTRIBUTED_SPOOL_ROOT={spool_root()},"
            f"CONFIG={ROOT / 'config.agentic_js.yml'},"
            f"POOL_PARTITION={partition}"
        ),
        str(script),
    ]

    if dry_run:
        return (
            f"DRY_RUN:{pool}:{partition}:"
            f"{time.time_ns()}"
        )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "sbatch failed"
        )

    return (
        result.stdout
        .strip()
        .split(";")[0]
    )


def _cancel(
    job_id: str,
    *,
    dry_run: bool,
) -> None:
    if dry_run:
        return

    subprocess.run(
        [
            "scancel",
            job_id,
        ],
        check=False,
    )


def _rank(
    policy: dict[str, Any],
    pool: str,
    partition: str,
) -> int:
    preferences = _pool_preferences(
        policy,
        pool,
    )

    try:
        return preferences.index(
            partition
        )
    except ValueError:
        return 999


def run_once(
    *,
    dry_run: bool,
) -> dict[str, Any]:
    spool = DistributedSpool(
        spool_root()
    )

    policy = load_pool_policy(
        spool.root
    )

    jobs = _jobs()
    active_ids = _active_job_ids(jobs)

    requeued_orphans = {
        pool: _requeue_orphaned_claims(
            spool,
            pool,
            active_ids,
        )
        for pool in SPECS
    }

    counts = {
        pool: spool.counts(pool)
        for pool in SPECS
    }

    previous_status: dict[str, Any] = {}

    previous_status_path = (
        spool.root
        / "status"
        / "autoscaler.json"
    )

    if previous_status_path.exists():
        try:
            previous_status = read_json(
                previous_status_path
            )
        except Exception:
            previous_status = {}

    (
        desired,
        target_reasons,
        allocation,
    ) = compute_targets(
        policy,
        counts,
        previous_status,
    )

    cancelled: dict[
        str,
        list[str],
    ] = {
        pool: []
        for pool in SPECS
    }

    errors: dict[
        str,
        list[str],
    ] = {
        pool: []
        for pool in SPECS
    }

    for pool in SPECS:
        active = _active_for_pool(
            jobs,
            pool,
        )

        enabled = pool_enabled(
            policy,
            pool,
        )

        if not enabled:
            targets = active
        else:
            excess = max(
                0,
                len(active) - desired[pool],
            )

            heartbeat_map = _heartbeat_by_job(
                spool,
                pool,
            )

            worst_rank = max(
                (
                    _rank(
                        policy,
                        pool,
                        job["partition"],
                    )
                    for job in active
                ),
                default=-1,
            )

            safe: list[
                dict[str, str]
            ] = []

            for job in active:
                if (
                    _rank(
                        policy,
                        pool,
                        job["partition"],
                    )
                    != worst_rank
                ):
                    continue

                if job["state"] == "PENDING":
                    safe.append(job)
                    continue

                base_id = (
                    job["job_id"]
                    .split("_", 1)[0]
                )

                heartbeat = (
                    heartbeat_map.get(
                        job["job_id"]
                    )
                    or heartbeat_map.get(
                        base_id
                    )
                )

                state = str(
                    (
                        heartbeat
                        or {}
                    ).get("state")
                    or ""
                ).lower()

                if state in {
                    "idle",
                    "stopped",
                    "error",
                }:
                    safe.append(job)

            safe.sort(
                key=lambda job: (
                    -_rank(
                        policy,
                        pool,
                        job["partition"],
                    ),
                    job["state"]
                    != "PENDING",
                )
            )

            targets = safe[:excess]

        for job in targets:
            try:
                _cancel(
                    job["job_id"],
                    dry_run=dry_run,
                )

                cancelled[pool].append(
                    job["job_id"]
                )
            except Exception as exc:
                errors[pool].append(
                    str(exc)
                )

    if any(cancelled.values()) and not dry_run:
        time.sleep(1)

    jobs = _jobs()

    worker_names = {
        alias
        for spec in SPECS.values()
        for alias in spec["aliases"]
    }

    occupancy: Counter[str] = Counter(
        job["partition"]
        for job in jobs
        if (
            job["state"] in ACTIVE_STATES
            and job["name"] in worker_names
        )
    )

    capacity = _partition_capacity()

    active_counts = {
        pool: len(
            _active_for_pool(
                jobs,
                pool,
            )
        )
        for pool in SPECS
    }

    deficits = {
        pool: max(
            0,
            desired[pool]
            - active_counts[pool],
        )
        for pool in SPECS
    }

    submitted: dict[
        str,
        list[dict[str, str]],
    ] = {
        pool: []
        for pool in SPECS
    }

    promotions: dict[
        str,
        list[dict[str, str]],
    ] = {
        pool: []
        for pool in SPECS
    }

    def submit_for_pool(
        pool: str,
        *,
        reason: str,
    ) -> bool:
        partition = _choose_partition(
            policy,
            pool,
            occupancy,
            capacity,
        )

        if partition is None:
            return False

        try:
            job_id = _submit(
                pool,
                partition,
                dry_run=dry_run,
            )
        except Exception as exc:
            errors[pool].append(
                str(exc)
            )
            return False

        row = {
            "job_id": job_id,
            "partition": partition,
            "reason": reason,
        }

        submitted[pool].append(row)

        if reason == "promotion":
            promotions[pool].append(row)

        jobs.append(
            {
                "job_id": job_id,
                "name": SPECS[pool][
                    "job_name"
                ],
                "state": "PENDING",
                "partition": partition,
            }
        )

        occupancy[partition] += 1
        active_counts[pool] += 1

        if deficits[pool] > 0:
            deficits[pool] -= 1

        return True

    pool_order = sorted(
        SPECS,
        key=lambda pool: int(
            policy["pools"][pool][
                "priority"
            ]
        ),
        reverse=True,
    )

    # Give every enabled pool with demand at least one worker
    # before distributing spare capacity.
    for pool in pool_order:
        if (
            deficits[pool] > 0
            and active_counts[pool] == 0
        ):
            submit_for_pool(
                pool,
                reason="minimum_share",
            )

    # Weighted sharing: high-priority pools receive more workers,
    # while a pool that already owns many nodes is progressively
    # deprioritized.
    for _ in range(128):
        candidates = [
            pool
            for pool in pool_order
            if deficits[pool] > 0
        ]

        if not candidates:
            break

        candidates.sort(
            key=lambda pool: (
                int(
                    policy["pools"][pool][
                        "priority"
                    ]
                )
                / max(
                    1,
                    active_counts[pool] + 1,
                )
            ),
            reverse=True,
        )

        made_progress = False

        for pool in candidates:
            if submit_for_pool(
                pool,
                reason="demand",
            ):
                made_progress = True
                break

        if not made_progress:
            break

    # Slurm cannot move a running job. Promotion starts one worker
    # on the best available partition. On a later cycle, once the
    # inferior worker becomes idle, the scale-down logic removes it.
    for pool in pool_order:
        if not pool_enabled(
            policy,
            pool,
        ):
            continue

        if desired[pool] <= 0:
            continue

        active = _active_for_pool(
            jobs,
            pool,
        )

        if len(active) != desired[pool]:
            continue

        current_best_rank = min(
            (
                _rank(
                    policy,
                    pool,
                    job["partition"],
                )
                for job in active
            ),
            default=999,
        )

        target = _choose_partition(
            policy,
            pool,
            occupancy,
            capacity,
        )

        if target is None:
            continue

        if (
            _rank(
                policy,
                pool,
                target,
            )
            >= current_best_rank
        ):
            continue

        submit_for_pool(
            pool,
            reason="promotion",
        )

    final_jobs = _jobs()

    status: dict[str, Any] = {
        "updated_at": time.time(),
        "dry_run": dry_run,
        "policy": policy,
        "allocation": allocation,
        "partition_limits": PARTITION_LIMITS,
        "partition_capacity": capacity,
        "partition_occupancy": dict(
            Counter(
                job["partition"]
                for job in final_jobs
                if (
                    job["state"] in ACTIVE_STATES
                    and job["name"] in worker_names
                )
            )
        ),
        "pools": {},
    }

    for pool in SPECS:
        active = _active_for_pool(
            final_jobs,
            pool,
        )

        enabled = pool_enabled(
            policy,
            pool,
        )

        decision = "steady"

        if not enabled:
            decision = (
                "stopping"
                if active
                else "paused"
            )
        elif promotions[pool]:
            decision = "promoting"
        elif submitted[pool]:
            decision = "scale_up"
        elif cancelled[pool]:
            decision = "scale_down"
        elif errors[pool]:
            decision = "error"

        status["pools"][pool] = {
            "enabled": enabled,
            "counts": spool.counts(pool),
            "active_workers": len(active),
            "desired_workers": desired[pool],
            "target_reason": target_reasons[pool],
            "partition_preferences": (
                _pool_preferences(
                    policy,
                    pool,
                )
            ),
            "jobs": active,
            "decision": decision,
            "submitted": submitted[pool],
            "promotions": promotions[pool],
            "cancelled": cancelled[pool],
            "requeued_orphans": (
                requeued_orphans[pool]
            ),
            "errors": errors[pool],
        }

    atomic_replace_json(
        spool.root
        / "status"
        / "autoscaler.json",
        status,
    )

    print(
        status,
        flush=True,
    )

    return status


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    while True:
        run_once(
            dry_run=args.dry_run
        )

        if args.once:
            return

        time.sleep(
            max(
                10,
                args.interval,
            )
        )


if __name__ == "__main__":
    main()
