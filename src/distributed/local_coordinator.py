from __future__ import annotations

import argparse
import os
import shutil
import signal
import sqlite3
import time
import traceback
import uuid
from pathlib import Path

import src.distributed.cheap_pipeline as cheap
import src.distributed.codeql_pipeline as codeql
import src.distributed.mining_pipeline as mining
from src.db.database import Database
from src.distributed.spool import DistributedSpool, atomic_replace_json
from src.distributed.pool_control import load_pool_policy, pool_enabled
from src.distributed.ui_commands import process_commands


ROOT = Path(
    "/home-mscluster/astrauss/new/"
    "malicious-issue-miner-rate-smart"
)

STOP_REQUESTED = False

# Full database publication is expensive on shared NFS. Atomic replacement
# provides reader consistency without an unbounded forced NFS fsync.
AUTHORITATIVE_PUBLISH_INTERVAL_SECONDS = max(
    60,
    int(os.getenv("AUTHORITATIVE_PUBLISH_INTERVAL_SECONDS", "900")),
)

# Shared NFS cannot reliably accept multi-gigabyte synchronous snapshots.
# Keep imports and mining running, but disable snapshot-dependent work until
# publication is moved into a separate SLURM job.
SNAPSHOT_PUBLICATION_ENABLED = (
    os.getenv("SNAPSHOT_PUBLICATION_ENABLED", "0").strip().lower()
    in {"1", "true", "yes", "on"}
)


def request_stop(
    signum: int,
    frame: object,
) -> None:
    global STOP_REQUESTED

    STOP_REQUESTED = True

    print(
        f"local coordinator stop requested signal={signum}",
        flush=True,
    )


def shared_db_path() -> Path:
    pointer = ROOT / ".current_agentic_js_eval_db"

    value = pointer.read_text(
        encoding="utf-8"
    ).strip()

    if not value:
        raise RuntimeError(
            "Active database pointer is empty"
        )

    return Path(value)


def local_db_path() -> Path:
    job_id = os.getenv(
        "SLURM_JOB_ID",
        "local",
    )

    base = Path(
        os.getenv(
            "SLURM_TMPDIR",
            f"/tmp/{os.getenv('USER', 'user')}/"
            f"distributed-coordinator-{job_id}",
        )
    )

    base.mkdir(
        parents=True,
        exist_ok=True,
    )

    return base / "authoritative.db"


def sqlite_backup(
    source: Path,
    destination: Path,
) -> None:
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = destination.with_name(
        f".{destination.name}."
        f"{os.getpid()}-{uuid.uuid4().hex}.tmp"
    )

    for suffix in (
        "",
        "-journal",
        "-wal",
        "-shm",
    ):
        candidate = Path(
            str(temporary) + suffix
        )

        try:
            candidate.unlink()
        except FileNotFoundError:
            pass

    source_connection = sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
        timeout=120,
    )

    destination_connection = sqlite3.connect(
        str(temporary),
        timeout=120,
    )

    try:
        source_connection.execute(
            "PRAGMA busy_timeout=120000"
        )

        destination_connection.execute(
            "PRAGMA busy_timeout=120000"
        )

        source_connection.backup(
            destination_connection,
            pages=1000,
            sleep=0.05,
        )

        destination_connection.execute(
            "PRAGMA journal_mode=DELETE"
        )

        destination_connection.commit()
        check = destination_connection.execute(
            "PRAGMA quick_check"
        ).fetchone()[0]
        if check != "ok":
            raise RuntimeError(
                f"SQLite snapshot quick_check failed: {check}"
            )

    finally:
        destination_connection.close()
        source_connection.close()

    os.replace(
        temporary,
        destination,
    )


def fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_RDONLY,
        )

        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    except OSError:
        pass


def publish_snapshot(
    source: Path,
    destination: Path,
) -> None:
    """Publish without creating a second full copy in SLURM_TMPDIR."""
    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shared_temporary = destination.with_name(
        f".{destination.name}."
        f"publish-{os.getenv('SLURM_JOB_ID', 'local')}-"
        f"{uuid.uuid4().hex}.tmp"
    )

    try:
        # Back up directly into the shared destination directory.
        # The former implementation first duplicated the complete
        # database beside the node-local source and exhausted
        # SLURM_TMPDIR.
        sqlite_backup(
            source,
            shared_temporary,
        )

        os.replace(
            shared_temporary,
            destination,
        )


        for suffix in (
            "-journal",
            "-wal",
            "-shm",
        ):
            try:
                Path(
                    str(destination) + suffix
                ).unlink()
            except FileNotFoundError:
                pass

    finally:
        for suffix in (
            "",
            "-journal",
            "-wal",
            "-shm",
        ):
            try:
                Path(
                    str(shared_temporary) + suffix
                ).unlink()
            except FileNotFoundError:
                pass


def reconcile_archived_results(
    db: Database,
    spool: DistributedSpool,
    pool: str,
) -> int:
    rows = db.query(
        """
        SELECT task_id
        FROM distributed_result_imports
        """
    )

    imported_ids = {
        str(row["task_id"])
        for row in rows
    }

    results_directory = spool.queue_path(
        pool,
        "results",
    )

    archive_directory = (
        results_directory
        / "imported"
    )

    if not archive_directory.exists():
        return 0

    restored = 0

    for archived in sorted(
        archive_directory.glob("*.json")
    ):
        if archived.name.startswith("."):
            continue

        task_id = archived.stem

        if task_id in imported_ids:
            continue

        destination = (
            results_directory
            / archived.name
        )

        if destination.exists():
            continue

        try:
            os.replace(
                archived,
                destination,
            )

            restored += 1

        except FileNotFoundError:
            continue

    return restored


def run(
    *,
    once: bool,
    interval: int,
) -> None:
    shared_database = shared_db_path()
    # FULL3809_DIRECT_SHARED_DB
    # The continuation DB is already the dedicated writable copy.
    # Keep exactly one SQLite writer: this coordinator.
    local_database = shared_database
    print(
        f"COORDINATOR_DB_MODE|mode=direct-shared|"
        f"path={local_database}|"
        f"bytes={local_database.stat().st_size}",
        flush=True,
    )

    print(
        f"COORDINATOR_LOCAL_DB|"
        f"shared={shared_database}|"
        f"local={local_database}|"
        f"shared_bytes={shared_database.stat().st_size}",
        flush=True,
    )

    working_database_ready = False

    if local_database.exists():
        try:
            with sqlite3.connect(str(local_database)) as connection:
                connection.execute("PRAGMA schema_version").fetchone()
            working_database_ready = True
            print(
                f"COORDINATOR_WORKING_DB|mode=reused|"
                f"path={local_database}|"
                f"bytes={local_database.stat().st_size}"
            )
        except sqlite3.DatabaseError:
            invalid_database = local_database.with_name(
                f"{local_database.name}.invalid-"
                f"{os.getenv('SLURM_JOB_ID', 'local')}"
            )
            os.replace(local_database, invalid_database)
            print(
                f"COORDINATOR_WORKING_DB_INVALID|"
                f"preserved={invalid_database}"
            )

    if not working_database_ready:
        sqlite_backup(shared_database, local_database)
        print(
            f"COORDINATOR_WORKING_DB|mode=created|"
            f"path={local_database}|"
            f"bytes={local_database.stat().st_size}"
        )
    db = Database(
        local_database,
        read_only=False,
        command_spool=None,
    )
    spool_root = Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(ROOT / "data/distributed_spool"),
        )
    )
    spool = DistributedSpool(spool_root)

    cheap.ensure_import_table(db)
    cheap.active_db_path = lambda: local_database
    codeql.active_db_path = lambda: local_database
    if SNAPSHOT_PUBLICATION_ENABLED:
        cheap.create_snapshot = publish_snapshot
        codeql.create_snapshot = publish_snapshot

    cheap_restored = reconcile_archived_results(
        db,
        spool,
        "cheap_analysis",
    )
    codeql_restored = reconcile_archived_results(
        db,
        spool,
        "codeql_security",
    )

    cheap_snapshot = spool_root / "snapshots" / "cheap-analysis.db"
    codeql_snapshot = spool_root / "snapshots" / "codeql-security.db"
    coordinator_status = spool_root / "status" / "coordinator.json"

    print(
        "local coordinator started "
        f"local_db={local_database} "
        f"shared_db={shared_database} "
        f"cheap_restored={cheap_restored} "
        f"codeql_restored={codeql_restored}",
        flush=True,
    )

    last_publish = time.monotonic()
    publish_pending = False

    while not STOP_REQUESTED:
        try:
            policy = load_pool_policy(spool.root)
            ui_processed = process_commands(db, spool)
            mining_imported = mining.import_results(db, spool)
            cheap_imported = cheap.import_results(db, spool)
            codeql_imported = codeql.import_results(db, spool)

            ui_requeued = spool.requeue_stale(
                "ui_commands",
                stale_seconds=5 * 60,
            )
            mining_requeued = spool.requeue_stale(
                "mining",
                stale_seconds=2 * 60 * 60,
            )
            cheap_requeued = spool.requeue_stale(
                "cheap_analysis",
                stale_seconds=4 * 60 * 60,
            )
            codeql_requeued = spool.requeue_stale(
                "codeql_security",
                stale_seconds=12 * 60 * 60,
            )

            mining_created = (
                mining.enqueue_jobs(spool, db)
                if pool_enabled(policy, "mining")
                else 0
            )
            cheap_created = (
                cheap.enqueue_jobs(
                    db,
                    spool,
                    cheap_snapshot,
                )
                if (
                    SNAPSHOT_PUBLICATION_ENABLED
                    and pool_enabled(policy, "cheap_analysis")
                )
                else 0
            )
            codeql_created = (
                codeql.enqueue_jobs(
                    db,
                    spool,
                    codeql_snapshot,
                )
                if (
                    SNAPSHOT_PUBLICATION_ENABLED
                    and pool_enabled(policy, "codeql_security")
                )
                else 0
            )

            changed = any(
                (
                    ui_processed,
                    mining_imported,
                    cheap_imported,
                    codeql_imported,
                    mining_created,
                    cheap_created,
                    codeql_created,
                )
            )

            now = time.monotonic()
            publish_pending = publish_pending or changed

            if (
                SNAPSHOT_PUBLICATION_ENABLED
                and publish_pending
                and now - last_publish
                >= AUTHORITATIVE_PUBLISH_INTERVAL_SECONDS
            ):
                publish_snapshot(local_database, shared_database)
                last_publish = now
                publish_pending = False

            status = {
                "updated_at": time.time(),
                "policy": policy,
                "local_database": str(local_database),
                "shared_database": str(shared_database),
                "last_publish_age_seconds": max(
                    0,
                    int(time.monotonic() - last_publish),
                ),
                "cycle": {
                    "ui_processed": ui_processed,
                    "mining_imported": mining_imported,
                    "cheap_imported": cheap_imported,
                    "codeql_imported": codeql_imported,
                    "mining_created": mining_created,
                    "cheap_created": cheap_created,
                    "codeql_created": codeql_created,
                    "ui_requeued": ui_requeued,
                    "mining_requeued": mining_requeued,
                    "cheap_requeued": cheap_requeued,
                    "codeql_requeued": codeql_requeued,
                },
                "pools": {
                    "mining": spool.counts("mining"),
                    "cheap_analysis": spool.counts("cheap_analysis"),
                    "codeql_security": spool.counts("codeql_security"),
                    "ui_commands": spool.counts("ui_commands"),
                },
            }
            atomic_replace_json(coordinator_status, status)

            print(
                "coordinator "
                f"ui_processed={ui_processed} "
                f"mining_imported={mining_imported} "
                f"cheap_imported={cheap_imported} "
                f"codeql_imported={codeql_imported} "
                f"mining_created={mining_created} "
                f"cheap_created={cheap_created} "
                f"codeql_created={codeql_created} "
                f"mining={spool.counts('mining')} "
                f"cheap={spool.counts('cheap_analysis')} "
                f"codeql={spool.counts('codeql_security')} "
                f"ui={spool.counts('ui_commands')}",
                flush=True,
            )

        except Exception:
            traceback.print_exc()
            print(
                "Coordinator cycle failed; local database retained and retrying",
                flush=True,
            )

        if once:
            break
        time.sleep(max(2, interval))

    print(
        "Coordinator stopped; persistent working database retained",
        flush=True,
    )

def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--once",
        action="store_true",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
    )

    args = parser.parse_args()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    run(
        once=args.once,
        interval=args.interval,
    )


if __name__ == "__main__":
    main()
