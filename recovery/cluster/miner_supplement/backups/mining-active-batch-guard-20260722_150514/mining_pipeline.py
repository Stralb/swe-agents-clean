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

    with db.connect() as target:
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


def enqueue_jobs(spool: DistributedSpool) -> int:
    if os.getenv("MINING_ENABLED", "1").lower() not in {"1", "true", "yes", "on"}:
        return 0

    shard_count = max(1, int(os.getenv("MINING_SHARDS", "4")))
    interval = max(300, int(os.getenv("MINING_PASS_INTERVAL_SECONDS", "3600")))
    bucket = int(time.time() // interval)
    created = 0

    imported = spool.queue_path(POOL, "results") / "imported"
    imported.mkdir(parents=True, exist_ok=True)

    for shard_index in range(shard_count):
        task_id = f"mining-{bucket}-{shard_index}-of-{shard_count}"
        if (imported / f"{task_id}.json").exists():
            continue
        if spool.enqueue(
            POOL,
            task_id,
            {
                "config_path": str(ROOT / "config.agentic_js.yml"),
                "shard_count": shard_count,
                "shard_index": shard_index,
                "max_seconds": int(os.getenv("MINING_TASK_MAX_SECONDS", "1800")),
                "max_repos": int(os.getenv("MINING_TASK_MAX_REPOS", "250")),
                "max_prs": int(os.getenv("MINING_TASK_MAX_PRS", "500")),
                "max_cases": int(os.getenv("MINING_TASK_MAX_CASES", "1000")),
            },
        ):
            created += 1
    return created


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
