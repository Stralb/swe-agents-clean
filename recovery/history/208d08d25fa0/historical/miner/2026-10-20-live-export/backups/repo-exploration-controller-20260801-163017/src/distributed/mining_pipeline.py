from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from src.db.database import Database
from src.distributed.spool import DistributedSpool, read_json
from src.pipeline.collect_pipeline import collect
from src.settings import load_settings
from src.workers.job_queue import (
    seed_codeql_security_jobs,
    seed_scanner_jobs,
    update_case_stages,
)

ROOT = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart")
POOL = "mining"


def spool_root() -> Path:
    return Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(ROOT / "data/distributed_spool"),
        )
    )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(connection, table):
        return []
    return [dict(row) for row in connection.execute(f'SELECT * FROM "{table}"')]


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")')
    }


def _insert_row(
    connection: sqlite3.Connection,
    table: str,
    row: dict[str, Any],
    *,
    mode: str = "IGNORE",
) -> None:
    available = _columns(connection, table)
    columns = [
        name
        for name in row
        if name != "id" and name in available
    ]
    if not columns:
        return
    placeholders = ",".join("?" for _ in columns)
    names = ",".join(f'"{name}"' for name in columns)
    connection.execute(
        f'INSERT OR {mode} INTO "{table}" ({names}) VALUES ({placeholders})',
        tuple(row[name] for name in columns),
    )


def _merge_worker_database(db: Database, artifact: Path) -> dict[str, int]:
    source = sqlite3.connect(
        f"file:{artifact}?mode=ro",
        uri=True,
        timeout=120,
    )
    source.row_factory = sqlite3.Row
    source.execute("PRAGMA query_only=ON")
    check = source.execute("PRAGMA quick_check").fetchone()[0]
    if check != "ok":
        source.close()
        raise RuntimeError(f"Mining artifact quick_check failed: {check}")

    counts: dict[str, int] = {}

    with db.transaction() as target:
        target.execute("PRAGMA foreign_keys=ON")

        repo_map: dict[int, int] = {}
        for row in _rows(source, "repos"):
            source_id = int(row["id"])
            _insert_row(target, "repos", row)
            found = target.execute(
                "SELECT id FROM repos WHERE full_name=?",
                (row["full_name"],),
            ).fetchone()
            if found:
                repo_map[source_id] = int(found[0])
        counts["repos"] = len(repo_map)

        for row in _rows(source, "repo_eligibility"):
            _insert_row(target, "repo_eligibility", row, mode="REPLACE")

        issue_map: dict[int, int] = {}
        for row in _rows(source, "issues"):
            source_id = int(row["id"])
            mapped_repo = repo_map.get(int(row["repo_id"]))
            if mapped_repo is None:
                continue
            row["repo_id"] = mapped_repo
            _insert_row(target, "issues", row)
            found = target.execute(
                "SELECT id FROM issues WHERE repo_id=? AND number=?",
                (mapped_repo, row["number"]),
            ).fetchone()
            if found:
                issue_map[source_id] = int(found[0])
        counts["issues"] = len(issue_map)

        pr_map: dict[int, int] = {}
        for row in _rows(source, "pull_requests"):
            source_id = int(row["id"])
            mapped_repo = repo_map.get(int(row["repo_id"]))
            if mapped_repo is None:
                continue
            row["repo_id"] = mapped_repo
            _insert_row(target, "pull_requests", row)
            found = target.execute(
                "SELECT id FROM pull_requests WHERE repo_id=? AND number=?",
                (mapped_repo, row["number"]),
            ).fetchone()
            if found:
                pr_map[source_id] = int(found[0])
        counts["pull_requests"] = len(pr_map)

        pr_file_map: dict[int, int] = {}
        for row in _rows(source, "pr_files"):
            source_id = int(row["id"])
            mapped_pr = pr_map.get(int(row["pr_id"]))
            if mapped_pr is None:
                continue
            row["pr_id"] = mapped_pr
            found = target.execute(
                "SELECT id FROM pr_files WHERE pr_id=? AND filename=? LIMIT 1",
                (mapped_pr, row.get("filename")),
            ).fetchone()
            if found is None:
                _insert_row(target, "pr_files", row)
                found = target.execute(
                    "SELECT id FROM pr_files WHERE pr_id=? AND filename=? ORDER BY id DESC LIMIT 1",
                    (mapped_pr, row.get("filename")),
                ).fetchone()
            if found:
                pr_file_map[source_id] = int(found[0])
        counts["pr_files"] = len(pr_file_map)

        for row in _rows(source, "issue_pr_links"):
            mapped_issue = issue_map.get(int(row["issue_id"]))
            mapped_pr = pr_map.get(int(row["pr_id"]))
            if mapped_issue is None or mapped_pr is None:
                continue
            row["issue_id"] = mapped_issue
            row["pr_id"] = mapped_pr
            _insert_row(target, "issue_pr_links", row)

        case_map: dict[int, int] = {}
        for row in _rows(source, "cases"):
            source_id = int(row["id"])
            mapped_repo = repo_map.get(int(row["repo_id"]))
            mapped_issue = issue_map.get(int(row["issue_id"]))
            mapped_pr = pr_map.get(int(row["pr_id"]))
            if None in (mapped_repo, mapped_issue, mapped_pr):
                continue
            row["repo_id"] = mapped_repo
            row["issue_id"] = mapped_issue
            row["pr_id"] = mapped_pr
            _insert_row(target, "cases", row)
            found = target.execute(
                "SELECT id FROM cases WHERE issue_id=? AND pr_id=?",
                (mapped_issue, mapped_pr),
            ).fetchone()
            if found:
                case_map[source_id] = int(found[0])
        counts["cases"] = len(case_map)

        for row in _rows(source, "upstream_features"):
            mapped_issue = issue_map.get(int(row["issue_id"]))
            if mapped_issue is None:
                continue
            row["issue_id"] = mapped_issue
            _insert_row(target, "upstream_features", row, mode="REPLACE")

        for row in _rows(source, "ai_markers"):
            for key, mapping in (
                ("case_id", case_map),
                ("issue_id", issue_map),
                ("pr_id", pr_map),
            ):
                value = row.get(key)
                if value is not None:
                    row[key] = mapping.get(int(value))
            _insert_row(target, "ai_markers", row)

        for row in _rows(source, "retrieval_queries"):
            _insert_row(target, "retrieval_queries", row)

        for row in _rows(source, "case_retrievals"):
            mapped_case = case_map.get(int(row["case_id"]))
            if mapped_case is None:
                continue
            row["case_id"] = mapped_case
            _insert_row(target, "case_retrievals", row)

        for row in _rows(source, "artifact_regions"):
            mapped_case = case_map.get(int(row["case_id"]))
            mapped_pr = pr_map.get(int(row["pr_id"]))
            if mapped_case is None or mapped_pr is None:
                continue
            row["case_id"] = mapped_case
            row["pr_id"] = mapped_pr
            if row.get("pr_file_id") is not None:
                row["pr_file_id"] = pr_file_map.get(int(row["pr_file_id"]))
            found = target.execute(
                "SELECT 1 FROM artifact_regions WHERE case_id=? AND path=? AND region=? LIMIT 1",
                (mapped_case, row.get("path"), row.get("region")),
            ).fetchone()
            if found is None:
                _insert_row(target, "artifact_regions", row)

        for row in _rows(source, "pr_region_profiles"):
            mapped_case = case_map.get(int(row["case_id"]))
            mapped_pr = pr_map.get(int(row["pr_id"]))
            if mapped_case is None or mapped_pr is None:
                continue
            row["case_id"] = mapped_case
            row["pr_id"] = mapped_pr
            _insert_row(target, "pr_region_profiles", row, mode="REPLACE")

        for row in _rows(source, "excluded_cases"):
            _insert_row(target, "excluded_cases", row)

        for row in _rows(source, "pipeline_events"):
            _insert_row(target, "pipeline_events", row)

    source.close()

    seed_scanner_jobs(db, include_codeql=False)
    seed_codeql_security_jobs(db)
    update_case_stages(db)
    return counts


# BEGIN DURABLE MINING REGRESSION GUARD
def _reload_live_mining_environment(
) -> dict[str, str]:
    """Reload MINING_* settings from .env.cluster."""

    values: dict[str, str] = {}
    environment_path = (
        ROOT / ".env.cluster"
    )

    if not environment_path.is_file():
        return values

    for raw_line in environment_path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        if line.startswith("export "):
            line = line[7:].strip()

        key, value = line.split(
            "=",
            1,
        )

        key = key.strip()
        value = value.strip()

        if not key.startswith("MINING_"):
            continue

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        values[key] = value
        os.environ[key] = value

    return values


def _current_mining_settings(
) -> dict[str, object]:
    import hashlib
    import json

    _reload_live_mining_environment()

    def integer(
        name: str,
        default: int,
        *,
        minimum: int = 1,
    ) -> int:
        try:
            parsed = int(
                os.getenv(
                    name,
                    str(default),
                )
            )
        except (TypeError, ValueError):
            parsed = default

        return max(
            minimum,
            parsed,
        )

    settings: dict[str, object] = {
        "enabled": (
            os.getenv(
                "MINING_ENABLED",
                "1",
            ).lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        ),
        "shard_count": integer(
            "MINING_SHARDS",
            4,
        ),
        "interval_seconds": integer(
            "MINING_PASS_INTERVAL_SECONDS",
            3600,
            minimum=300,
        ),
        "max_seconds": integer(
            "MINING_TASK_MAX_SECONDS",
            1800,
        ),
        "max_repos": integer(
            "MINING_TASK_MAX_REPOS",
            250,
        ),
        "max_prs": integer(
            "MINING_TASK_MAX_PRS",
            500,
        ),
        "max_cases": integer(
            "MINING_TASK_MAX_CASES",
            1000,
        ),
    }

    encoded = json.dumps(
        settings,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    settings["config_revision"] = (
        hashlib.sha256(
            encoded
        ).hexdigest()[:16]
    )

    return settings


def _active_mining_records(
    spool: DistributedSpool,
) -> list[dict[str, object]]:
    import json
    import re

    records: list[dict[str, object]] = []

    for state in (
        "pending",
        "claimed",
    ):
        directory = (
            spool.root
            / POOL
            / state
        )

        if not directory.exists():
            continue

        for task_path in sorted(
            directory.glob("*.json")
        ):
            try:
                envelope = json.loads(
                    task_path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception as exc:
                records.append({
                    "state": state,
                    "path": str(task_path),
                    "error": str(exc),
                })

                continue

            task_id = str(
                envelope.get("task_id")
                or ""
            )

            match = re.fullmatch(
                r"(.+)-(\d+)-of-(\d+)",
                task_id,
            )

            if match is None:
                continue

            payload = envelope.get(
                "payload",
                {},
            )

            if not isinstance(
                payload,
                dict,
            ):
                payload = {}

            records.append({
                "state": state,
                "path": str(task_path),
                "task_id": task_id,
                "batch_id": match.group(1),
                "shard_index": int(
                    match.group(2)
                ),
                "shard_count": int(
                    match.group(3)
                ),
                "payload": payload,
            })

    return records


def _write_mining_guard_status(
    spool: DistributedSpool,
    payload: dict[str, object],
) -> None:
    import json
    import uuid

    destination = (
        spool.root
        / "status"
        / "mining_batch_guard.json"
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        "."
        + destination.name
        + "."
        + uuid.uuid4().hex
        + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": time.time(),
                **payload,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary,
        destination,
    )


def _mining_task_exists(
    spool: DistributedSpool,
    task_id: str,
) -> bool:
    directories = (
        (
            spool.root
            / POOL
            / "pending"
        ),
        (
            spool.root
            / POOL
            / "claimed"
        ),
        (
            spool.root
            / POOL
            / "results"
        ),
        (
            spool.root
            / POOL
            / "results"
            / "imported"
        ),
        (
            spool.root
            / POOL
            / "failed"
        ),
    )

    for directory in directories:
        if not directory.exists():
            continue

        if any(
            directory.glob(
                task_id + "*.json"
            )
        ):
            return True

    return False


def enqueue_jobs(
    spool: DistributedSpool,
) -> int:
    settings = _current_mining_settings()

    if not bool(
        settings["enabled"]
    ):
        _write_mining_guard_status(
            spool,
            {
                "state": "disabled",
                "desired": settings,
            },
        )

        return 0

    desired_shards = int(
        settings["shard_count"]
    )

    active = _active_mining_records(
        spool
    )

    unreadable = [
        record
        for record in active
        if "error" in record
    ]

    if unreadable:
        _write_mining_guard_status(
            spool,
            {
                "state": "unreadable_active_task",
                "desired": settings,
                "records": unreadable,
                "action": (
                    "Enqueue blocked. Existing "
                    "task files were not changed."
                ),
            },
        )

        print(
            "Mining enqueue blocked: "
            "unreadable active task file",
            flush=True,
        )

        return 0

    if active:
        batch_ids = sorted({
            str(record["batch_id"])
            for record in active
        })

        shard_counts = sorted({
            int(record["shard_count"])
            for record in active
        })

        mismatches: dict[str, object] = {}

        if len(batch_ids) != 1:
            mismatches[
                "active_batches"
            ] = batch_ids

        if shard_counts != [
            desired_shards
        ]:
            mismatches[
                "shard_count"
            ] = {
                "active": shard_counts,
                "desired": desired_shards,
            }

        limits = {
            "max_seconds": int(
                settings["max_seconds"]
            ),
            "max_repos": int(
                settings["max_repos"]
            ),
            "max_prs": int(
                settings["max_prs"]
            ),
            "max_cases": int(
                settings["max_cases"]
            ),
        }

        for name, desired_value in (
            limits.items()
        ):
            observed: set[int] = set()

            for record in active:
                payload = record.get(
                    "payload",
                    {},
                )

                if (
                    not isinstance(
                        payload,
                        dict,
                    )
                    or name not in payload
                ):
                    continue

                try:
                    observed.add(
                        int(payload[name])
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    continue

            if (
                observed
                and observed != {
                    desired_value
                }
            ):
                mismatches[name] = {
                    "active": sorted(
                        observed
                    ),
                    "desired": desired_value,
                }

        if mismatches:
            _write_mining_guard_status(
                spool,
                {
                    "state": (
                        "configuration_mismatch"
                    ),
                    "desired": settings,
                    "active_batches": batch_ids,
                    "active_tasks": len(active),
                    "mismatches": mismatches,
                    "action": (
                        "Enqueue blocked. Existing "
                        "tasks were not changed."
                    ),
                },
            )

            print(
                "Mining enqueue blocked by "
                "configuration guard: "
                + repr(mismatches),
                flush=True,
            )

            return 0

        _write_mining_guard_status(
            spool,
            {
                "state": "active",
                "desired": settings,
                "active_batch": batch_ids[0],
                "active_tasks": len(active),
                "pending_tasks": sum(
                    record["state"]
                    == "pending"
                    for record in active
                ),
                "claimed_tasks": sum(
                    record["state"]
                    == "claimed"
                    for record in active
                ),
            },
        )

        return 0

    interval = int(
        settings["interval_seconds"]
    )

    bucket = int(
        time.time() // interval
    )

    batch_id = f"mining-{bucket}"
    created = 0

    for shard_index in range(
        desired_shards
    ):
        task_id = (
            f"{batch_id}-"
            f"{shard_index}-of-"
            f"{desired_shards}"
        )

        if _mining_task_exists(
            spool,
            task_id,
        ):
            continue

        if spool.enqueue(
            POOL,
            task_id,
            {
                "config_path": str(
                    ROOT
                    / "config.agentic_js.yml"
                ),
                "shard_count": (
                    desired_shards
                ),
                "shard_index": shard_index,
                "max_seconds": int(
                    settings["max_seconds"]
                ),
                "max_repos": int(
                    settings["max_repos"]
                ),
                "max_prs": int(
                    settings["max_prs"]
                ),
                "max_cases": int(
                    settings["max_cases"]
                ),
                "config_revision": str(
                    settings[
                        "config_revision"
                    ]
                ),
            },
        ):
            created += 1

    _write_mining_guard_status(
        spool,
        {
            "state": (
                "created"
                if created
                else "complete_for_interval"
            ),
            "desired": settings,
            "batch": {
                "batch_id": batch_id,
                "shard_count": (
                    desired_shards
                ),
                "created_tasks": created,
            },
        },
    )

    if created:
        print(
            "Mining batch created "
            f"batch={batch_id} "
            f"shards={desired_shards} "
            f"created={created} "
            "config_revision="
            + str(
                settings[
                    "config_revision"
                ]
            ),
            flush=True,
        )

    return created


# END DURABLE MINING REGRESSION GUARD


def import_results(db: Database, spool: DistributedSpool) -> int:
    results = spool.queue_path(POOL, "results")
    archive = results / "imported"
    archive.mkdir(parents=True, exist_ok=True)
    imported = 0
    root = spool.root.resolve()

    for path in sorted(results.glob("*.json")):
        envelope = read_json(path)
        artifact_value = str(envelope.get("result", {}).get("artifact_path") or "")
        if not artifact_value:
            raise RuntimeError(f"Mining result has no artifact_path: {path}")
        artifact = Path(artifact_value).resolve()
        if not artifact.is_relative_to(root):
            raise RuntimeError(f"Mining artifact escaped spool root: {artifact}")
        if not artifact.exists():
            raise RuntimeError(f"Mining artifact is missing: {artifact}")

        counts = _merge_worker_database(db, artifact)
        destination = archive / path.name
        os.replace(path, destination)
        imported += 1
        print(
            f"mining imported task={path.stem} counts={counts}",
            flush=True,
        )
    return imported


def _copy_sqlite(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.unlink(missing_ok=True)
    source_connection = sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
        timeout=120,
    )
    destination_connection = sqlite3.connect(str(temporary), timeout=120)
    try:
        source_connection.backup(destination_connection, pages=1000, sleep=0.05)
        destination_connection.commit()
        check = destination_connection.execute("PRAGMA quick_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"Worker DB quick_check failed: {check}")
    finally:
        destination_connection.close()
        source_connection.close()
    os.replace(temporary, destination)


def _heartbeat_loop(
    spool: DistributedSpool,
    worker_id: str,
    task_id: str,
    stop: threading.Event,
) -> None:
    while not stop.wait(30):
        spool.heartbeat(
            POOL,
            worker_id,
            state="working",
            task_id=task_id,
            detail="Mining collection pass running",
        )


def _run_claim(
    spool: DistributedSpool,
    worker_id: str,
    claim: Any,
) -> dict[str, Any]:
    payload = dict(claim.payload.get("payload") or {})
    local_root = Path(
        os.getenv(
            "SLURM_TMPDIR",
            f"/tmp/{os.getenv('USER', 'user')}/mining-{os.getpid()}",
        )
    ) / claim.task_id
    local_root.mkdir(parents=True, exist_ok=True)
    local_db = local_root / "mining.db"

    Database(
        local_db,
        read_only=False,
        command_spool=None,
    ).init_schema(ROOT / "src/db/schema.sql")

    os.environ["CONFIG"] = str(payload.get("config_path") or ROOT / "config.agentic_js.yml")
    os.environ["DB_PATH"] = str(local_db)

    # BEGIN PYTHON RUNTIME REPOSITORY SEED
    if not str(os.environ.get(
        "MINING_REPO_SEED_DB",
        "",
    ) or "").strip():
        from pathlib import Path as _MiningSeedPath

        _mining_root = (
            _MiningSeedPath(__file__)
            .resolve()
            .parents[2]
        )

        _seed_pointer = (
            _mining_root
            / ".current_agentic_js_eval_db"
        )

        if _seed_pointer.is_file():
            _seed_value = _seed_pointer.read_text(
                encoding="utf-8"
            ).strip()

            if _seed_value:
                _seed_path = _MiningSeedPath(
                    _seed_value
                )

                if not _seed_path.is_absolute():
                    _seed_path = (
                        _mining_root
                        / _seed_path
                    ).resolve()

                if _seed_path.is_file():
                    os.environ["MINING_REPO_SEED_DB"] = str(_seed_path)
                    print(
                        "MINING_REPO_SEED_DB="
                        + str(_seed_path),
                        flush=True,
                    )
    # END PYTHON RUNTIME REPOSITORY SEED
    os.environ["REPO_SHARD_COUNT"] = str(payload["shard_count"])
    os.environ["REPO_SHARD_INDEX"] = str(payload["shard_index"])
    os.environ["MAX_SECONDS"] = str(payload["max_seconds"])
    os.environ["MAX_REPOS"] = str(payload["max_repos"])
    os.environ["MAX_PRS"] = str(payload["max_prs"])
    os.environ["MAX_CASES"] = str(payload["max_cases"])

    stop = threading.Event()
    thread = threading.Thread(
        target=_heartbeat_loop,
        args=(spool, worker_id, claim.task_id, stop),
        daemon=True,
    )
    thread.start()
    try:
        collect(load_settings())
    finally:
        stop.set()
        thread.join(timeout=5)

    artifact = (
        spool.root
        / POOL
        / "artifacts"
        / f"{claim.task_id}-{uuid.uuid4().hex}.db"
    )
    _copy_sqlite(local_db, artifact)
    shutil.rmtree(local_root, ignore_errors=True)
    return {
        "artifact_path": str(artifact),
        "shard_count": int(payload["shard_count"]),
        "shard_index": int(payload["shard_index"]),
    }


def worker(*, idle_seconds: int, max_idle_cycles: int) -> None:
    spool = DistributedSpool(spool_root())
    worker_id = (
        f"mining-{os.getenv('SLURM_JOB_ID', 'local')}-"
        f"{os.getenv('SLURM_ARRAY_TASK_ID', '0')}-"
        f"{os.uname().nodename}-{os.getpid()}"
    )
    idle_cycles = 0
    spool.heartbeat(POOL, worker_id, state="idle", detail="Worker started")

    while idle_cycles < max_idle_cycles:
        claim = spool.claim(POOL, worker_id)
        if claim is None:
            idle_cycles += 1
            spool.heartbeat(
                POOL,
                worker_id,
                state="idle",
                detail=f"No task; idle cycle {idle_cycles}/{max_idle_cycles}",
            )
            time.sleep(max(1, idle_seconds))
            continue

        idle_cycles = 0
        try:
            result = _run_claim(spool, worker_id, claim)
            spool.publish_result(claim, result)
            print(f"worker={worker_id} task={claim.task_id} status=ok", flush=True)
        except Exception as exc:
            traceback.print_exc()
            spool.publish_failure(claim, str(exc))
            print(f"worker={worker_id} task={claim.task_id} status=error", flush=True)

    spool.heartbeat(POOL, worker_id, state="stopped", detail="Worker exiting")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    worker_parser = subparsers.add_parser("worker")
    worker_parser.add_argument("--idle-seconds", type=int, default=20)
    worker_parser.add_argument("--max-idle-cycles", type=int, default=180)

    args = parser.parse_args()
    if args.command == "worker":
        worker(
            idle_seconds=args.idle_seconds,
            max_idle_cycles=args.max_idle_cycles,
        )


if __name__ == "__main__":
    main()
