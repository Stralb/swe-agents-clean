#!/usr/bin/env python3
"""Observe the distributed miner and decide whether it is moving or stuck.

Uses only the Python standard library and read-only Slurm/filesystem commands.
It never submits, cancels, requeues, edits, or deletes jobs/files.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POOLS = ("mining", "cheap_analysis", "codeql_security")
STATES = ("pending", "claimed", "results", "failed")
ACTIVE_STATES = {"R", "PD", "CG", "CF", "RUNNING", "PENDING", "COMPLETING", "CONFIGURING"}
JOB_POOL = {
    "mim-mining-worker": "mining",
    "miner-mining": "mining",
    "mim-cheap-worker": "cheap_analysis",
    "miner-dist-cheap": "cheap_analysis",
    "mim-codeql-worker": "codeql_security",
    "miner-dist-codeql": "codeql_security",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(command: list[str], timeout: int = 15) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"command not found: {command[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", f"timed out after {timeout}s: {' '.join(command)}"
    except Exception as exc:
        return 1, "", f"{type(exc).__name__}: {exc}"


def direct_files(path: Path) -> list[Path]:
    try:
        return [item for item in path.iterdir() if item.is_file()]
    except (FileNotFoundError, NotADirectoryError, PermissionError, OSError):
        return []


def newest_file(path: Path) -> tuple[str, float, int]:
    newest: Path | None = None
    newest_mtime = 0.0
    newest_size = 0
    for item in direct_files(path):
        try:
            stat = item.stat()
        except OSError:
            continue
        if stat.st_mtime >= newest_mtime:
            newest = item
            newest_mtime = stat.st_mtime
            newest_size = stat.st_size
    return (newest.name if newest else "-", newest_mtime, newest_size)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else {"value": value}


def short(value: Any, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def useful_fields(value: Any, prefix: str = "", depth: int = 0) -> list[tuple[str, str]]:
    wanted = re.compile(
        r"(^|_)(task|task_id|id|repo|repository|owner|issue|issue_number|number|url|stage|status|worker|job|shard|cursor|query|language|claimed_by|started_at|updated_at)($|_)",
        re.IGNORECASE,
    )
    rows: list[tuple[str, str]] = []
    if depth > 3:
        return rows
    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if wanted.search(str(key)) and not isinstance(child, (dict, list)):
                rows.append((name, short(child)))
            elif isinstance(child, (dict, list)):
                rows.extend(useful_fields(child, name, depth + 1))
    elif isinstance(value, list):
        for index, child in enumerate(value[:5]):
            rows.extend(useful_fields(child, f"{prefix}[{index}]", depth + 1))
    return rows[:18]


@dataclass
class Job:
    job_id: str
    name: str
    state: str
    partition: str
    elapsed: str
    reason: str


def slurm_jobs() -> tuple[list[Job], list[str]]:
    errors: list[str] = []
    code, output, error = run(
        ["squeue", "-h", "-u", os.getenv("USER", ""), "-o", "%i|%j|%t|%P|%M|%R"]
    )
    if code != 0:
        errors.append(error.strip() or f"squeue returned {code}")
        return [], errors
    jobs: list[Job] = []
    for line in output.splitlines():
        parts = line.split("|", 5)
        if len(parts) == 6:
            jobs.append(Job(*[part.strip() for part in parts]))
    return jobs, errors


def worker_usage(job_id: str) -> str:
    code, output, _ = run(
        [
            "sstat",
            "-j",
            f"{job_id}.batch",
            "-n",
            "-P",
            "-o",
            "JobID,AveCPU,AveRSS,MaxRSS,MaxDiskRead,MaxDiskWrite",
        ]
    )
    if code != 0 or not output.strip():
        return "unavailable"
    return short(output.splitlines()[0], 220)


def newest_heartbeats(root: Path, pool: str) -> list[dict[str, Any]]:
    directory = root / pool / "heartbeats"
    candidates: list[tuple[float, Path]] = []
    for path in direct_files(directory):
        try:
            candidates.append((path.stat().st_mtime, path))
        except OSError:
            continue
    rows: list[dict[str, Any]] = []
    for mtime, path in sorted(candidates, reverse=True)[:8]:
        data = read_json(path) or {}
        raw_updated = data.get("updated_at")
        try:
            updated = float(raw_updated) if raw_updated is not None else mtime
        except (TypeError, ValueError):
            updated = mtime
        rows.append(
            {
                "file": path.name,
                "mtime": mtime,
                "updated": updated,
                "age": max(0.0, time.time() - updated),
                "job_id": str(data.get("slurm_job_id") or data.get("job_id") or ""),
                "fields": useful_fields(data),
            }
        )
    return rows


def policy_from_autoscaler(project: Path, jobs: list[Job]) -> dict[str, Any]:
    autoscaler_ids = [job.job_id for job in jobs if "autoscaler" in job.name.lower()]
    paths: list[Path] = []
    for job_id in autoscaler_ids:
        paths.append(project / "logs" / f"pool-autoscaler-{job_id}.out")
    paths.extend(sorted((project / "logs").glob("pool-autoscaler-*.out"), reverse=True)[:3])
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in reversed(lines[-80:]):
            if "'policy':" not in line and '"policy":' not in line:
                continue
            try:
                value = ast.literal_eval(line)
            except (SyntaxError, ValueError):
                try:
                    value = json.loads(line)
                except (ValueError, TypeError):
                    continue
            if isinstance(value, dict):
                return value
    return {}


@dataclass
class Snapshot:
    taken_at: float
    counts: dict[str, dict[str, int]]
    newest: dict[str, dict[str, tuple[str, float, int]]]
    jobs: list[Job]
    usage: dict[str, str]
    heartbeats: dict[str, list[dict[str, Any]]]
    claimed: dict[str, list[str]]
    errors: list[str] = field(default_factory=list)


def take_snapshot(spool: Path) -> Snapshot:
    counts: dict[str, dict[str, int]] = {}
    newest: dict[str, dict[str, tuple[str, float, int]]] = {}
    claimed: dict[str, list[str]] = {}
    for pool in POOLS:
        counts[pool] = {}
        newest[pool] = {}
        for state in STATES:
            directory = spool / pool / state
            files = direct_files(directory)
            counts[pool][state] = len(files)
            newest[pool][state] = newest_file(directory)
        claimed[pool] = sorted(path.name for path in direct_files(spool / pool / "claimed"))
    jobs, errors = slurm_jobs()
    usage = {
        job.job_id: worker_usage(job.job_id)
        for job in jobs
        if job.name in JOB_POOL and job.state in {"R", "CG"}
    }
    heartbeats = {pool: newest_heartbeats(spool, pool) for pool in POOLS}
    return Snapshot(time.time(), counts, newest, jobs, usage, heartbeats, claimed, errors)


def age_text(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"
    return f"{int(seconds // 3600)}h{int((seconds % 3600) // 60):02d}m"


def print_snapshot(snapshot: Snapshot, number: int) -> None:
    print(f"\n===== SAMPLE {number} @ {utc_now()} =====", flush=True)
    for pool in POOLS:
        values = " ".join(f"{state}={snapshot.counts[pool][state]}" for state in STATES)
        hb = snapshot.heartbeats[pool][0] if snapshot.heartbeats[pool] else None
        hb_text = f"newest_heartbeat_age={age_text(hb['age'])}" if hb else "newest_heartbeat=none"
        print(f"QUEUE  {pool:<17} {values} {hb_text}")
    for job in snapshot.jobs:
        marker = "WORKER" if job.name in JOB_POOL else "JOB"
        print(
            f"{marker:<6} id={job.job_id} name={job.name} state={job.state} "
            f"partition={job.partition} elapsed={job.elapsed} reason={job.reason}"
        )
        if job.job_id in snapshot.usage:
            print(f"       usage={snapshot.usage[job.job_id]}")
    for pool in POOLS:
        if snapshot.claimed[pool]:
            print(f"CLAIM  {pool}: {', '.join(snapshot.claimed[pool][:6])}")
    for error in snapshot.errors:
        print(f"WARN   {error}")
    sys.stdout.flush()


def show_claim_details(spool: Path, snapshot: Snapshot) -> None:
    print("\n===== CURRENT CLAIMED TASKS =====")
    found = False
    for pool in POOLS:
        for filename in snapshot.claimed[pool][:10]:
            found = True
            path = spool / pool / "claimed" / filename
            data = read_json(path)
            print(f"{pool}/{filename}")
            fields = useful_fields(data or {})
            if fields:
                for key, value in fields:
                    print(f"  {key}={value}")
            else:
                try:
                    print(f"  raw={short(path.read_text(encoding='utf-8', errors='replace'), 500)}")
                except OSError as exc:
                    print(f"  unreadable={exc}")
    if not found:
        print("none")


def changed(first: Snapshot, last: Snapshot, pool: str) -> list[str]:
    changes: list[str] = []
    for state in STATES:
        before = first.counts[pool][state]
        after = last.counts[pool][state]
        if before != after:
            changes.append(f"{state} {before}->{after}")
        before_newest = first.newest[pool][state]
        after_newest = last.newest[pool][state]
        if before_newest != after_newest and before == after:
            changes.append(f"{state} newest artifact changed")
    if first.claimed[pool] != last.claimed[pool]:
        changes.append("claimed task identity changed")
    return changes


def active_workers(snapshot: Snapshot, pool: str) -> list[Job]:
    return [
        job
        for job in snapshot.jobs
        if JOB_POOL.get(job.name) == pool and job.state in ACTIVE_STATES
    ]


def running_workers(snapshot: Snapshot, pool: str) -> list[Job]:
    return [job for job in active_workers(snapshot, pool) if job.state in {"R", "CG", "RUNNING", "COMPLETING"}]


def heartbeat_fresh(snapshot: Snapshot, pool: str, threshold: int) -> bool:
    return bool(snapshot.heartbeats[pool] and snapshot.heartbeats[pool][0]["age"] <= threshold)


def cpu_changed(first: Snapshot, last: Snapshot, pool: str) -> bool:
    common = {job.job_id for job in running_workers(first, pool)} & {
        job.job_id for job in running_workers(last, pool)
    }
    return any(
        first.usage.get(job_id) not in (None, "unavailable")
        and last.usage.get(job_id) not in (None, "unavailable")
        and first.usage.get(job_id) != last.usage.get(job_id)
        for job_id in common
    )


def report_check(status: str, name: str, detail: str) -> None:
    print(f"{status:<5} {name:<27} {detail}")


def final_report(project: Path, spool: Path, samples: list[Snapshot], stale_seconds: int) -> int:
    first, last = samples[0], samples[-1]
    policy = policy_from_autoscaler(project, last.jobs)
    print("\n===== HEALTH TESTS =====")

    coordinator = [job for job in last.jobs if "coordinator" in job.name.lower()]
    autoscaler = [job for job in last.jobs if "autoscaler" in job.name.lower()]
    report_check("PASS" if coordinator else "FAIL", "coordinator job", short(coordinator[0] if coordinator else "not found"))
    report_check("PASS" if autoscaler else "FAIL", "autoscaler job", short(autoscaler[0] if autoscaler else "not found"))

    overall_fail = not coordinator or not autoscaler
    any_progress = False
    for pool in POOLS:
        pool_changes = changed(first, last, pool)
        pending = last.counts[pool]["pending"]
        claimed_count = last.counts[pool]["claimed"]
        workers = active_workers(last, pool)
        runners = running_workers(last, pool)
        fresh = heartbeat_fresh(last, pool, stale_seconds)
        cpu_moves = cpu_changed(first, last, pool)
        if pool_changes:
            any_progress = True
            report_check("PASS", f"{pool} movement", "; ".join(pool_changes))
        elif claimed_count and runners and fresh and cpu_moves:
            report_check("PASS", f"{pool} active work", "same task; heartbeat fresh; CPU/I/O counters changed")
        elif claimed_count and runners and fresh:
            report_check("WARN", f"{pool} active work", "same task; heartbeat fresh; usage counters did not prove movement")
        elif claimed_count and not runners:
            overall_fail = True
            report_check("FAIL", f"{pool} orphan claim", f"claimed={claimed_count} but no running worker")
        elif claimed_count and not fresh:
            overall_fail = True
            report_check("FAIL", f"{pool} stale claim", f"claimed={claimed_count}; heartbeat older than {stale_seconds}s")
        elif pending and not workers:
            overall_fail = True
            report_check("FAIL", f"{pool} blocked backlog", f"pending={pending}; no active/pending worker")
        elif pending and workers and not runners:
            reason = "; ".join(f"{job.job_id}:{job.reason}" for job in workers)
            report_check("WARN", f"{pool} queued workers", f"pending={pending}; {reason}")
        elif pending and runners:
            report_check("WARN", f"{pool} no transition", f"pending={pending}; running worker exists but no measured transition")
        else:
            report_check("PASS", f"{pool} queue", "idle/empty")

    policy_pools = ((policy.get("policy") or {}).get("pools") or {}) if policy else {}
    observed_pools = (policy.get("pools") or {}) if policy else {}
    print("\n===== AUTOSCALER POLICY =====")
    if not policy:
        report_check("WARN", "policy visibility", "could not parse a recent autoscaler decision")
    for pool in POOLS:
        configured = policy_pools.get(pool) or {}
        observed = observed_pools.get(pool) or {}
        if not configured and not observed:
            continue
        enabled = configured.get("enabled")
        preferences = configured.get("partition_preferences") or observed.get("partition_preferences") or []
        decision = observed.get("decision", "unknown")
        errors = observed.get("errors") or []
        status = "PASS" if enabled is True else "WARN"
        report_check(
            status,
            pool,
            f"enabled={enabled} partitions={preferences} decision={decision} errors={short(errors)}",
        )

    show_claim_details(spool, last)
    print("\n===== VERDICT =====")
    if overall_fail:
        print("BLOCKED_OR_STUCK: at least one required service/worker/claim check failed.")
        return 2
    if any_progress:
        print("MOVING: queue artifacts changed during the observation window.")
        return 0
    if any(last.counts[pool]["claimed"] for pool in POOLS):
        print("WORKING_BUT_NO_COMPLETION_YET: a claimed task is active; inspect heartbeat/usage warnings above.")
        return 0
    if any(last.counts[pool]["pending"] for pool in POOLS):
        print("WAITING: backlog exists and workers are queued/running, but no queue transition was observed.")
        return 1
    print("IDLE: no pending or claimed tasks exist.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    parser.add_argument("--samples", type=int, default=7, help="number of samples (default: 7)")
    parser.add_argument("--interval", type=int, default=30, help="seconds between samples (default: 30)")
    parser.add_argument("--stale-seconds", type=int, default=180, help="heartbeat age treated as stale (default: 180)")
    parser.add_argument("--once", action="store_true", help="take one snapshot without waiting")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = args.project.expanduser().resolve()
    spool = Path(os.getenv("DISTRIBUTED_SPOOL_ROOT", str(project / "data" / "distributed_spool"))).expanduser()
    sample_count = 1 if args.once else max(2, args.samples)
    interval = max(1, args.interval)
    print("===== MINER WATCHDOG =====")
    print(f"project={project}")
    print(f"spool={spool}")
    print(f"samples={sample_count} interval={interval}s observation={(sample_count - 1) * interval}s")
    print("mode=read-only (no sbatch/scancel/scontrol update/file writes)")
    if not spool.is_dir():
        print(f"FATAL: spool directory does not exist: {spool}")
        return 2
    samples: list[Snapshot] = []
    for index in range(1, sample_count + 1):
        snapshot = take_snapshot(spool)
        samples.append(snapshot)
        print_snapshot(snapshot, index)
        if index < sample_count:
            print(f"Waiting {interval}s for measurable movement...", flush=True)
            time.sleep(interval)
    return final_report(project, spool, samples, max(30, args.stale_seconds))


if __name__ == "__main__":
    raise SystemExit(main())
