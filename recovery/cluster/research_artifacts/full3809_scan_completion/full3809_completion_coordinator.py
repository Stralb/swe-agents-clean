from __future__ import annotations

import json
import os
import signal
import sqlite3
import sys
import time
import traceback
import uuid
from pathlib import Path

import src.distributed.cheap_pipeline as cheap
import src.distributed.codeql_pipeline as codeql

from src.db.database import Database
from src.distributed.local_coordinator import reconcile_archived_results
from src.distributed.spool import DistributedSpool


STOP = False

JOB_TYPES = (
    "semgrep_source",
    "secret_ci",
    "dependency_downgrade",
    "osv_dependency",
    "trivy_dependency",
    "codeql_security",
)


def request_stop(signum: int, frame: object) -> None:
    global STOP
    STOP = True
    print(
        f"FULL3809_STOP_REQUESTED signal={signum}",
        flush=True,
    )


def unfinished_state(
    database: Path,
) -> tuple[int, int, dict[str, int]]:
    placeholders = ",".join(
        "?"
        for _ in JOB_TYPES
    )

    with sqlite3.connect(
        str(database),
        timeout=120,
    ) as connection:
        rows = connection.execute(
            f"""
            SELECT
                status,
                COUNT(*)
            FROM scanner_jobs
            WHERE job_type IN ({placeholders})
            GROUP BY status
            """,
            JOB_TYPES,
        ).fetchall()

    counts = {
        str(status): int(count)
        for status, count in rows
    }

    unfinished = sum(
        counts.get(status, 0)
        for status in (
            "pending",
            "retry",
            "queued",
        )
    )

    errors = counts.get(
        "error",
        0,
    )

    return (
        unfinished,
        errors,
        counts,
    )


def queue_active(
    counts: dict[str, int],
) -> int:
    return sum(
        int(counts.get(name, 0))
        for name in (
            "pending",
            "claimed",
            "results",
        )
    )


def write_json(
    path: Path,
    payload: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    os.replace(
        temporary,
        path,
    )


def publish_database(
    source: Path,
    destination: Path,
) -> None:
    temporary = destination.with_name(
        f".{destination.name}."
        f"full3809-publish-"
        f"{os.getenv('SLURM_JOB_ID', 'local')}-"
        f"{uuid.uuid4().hex}.tmp"
    )

    for suffix in (
        "",
        "-journal",
        "-wal",
        "-shm",
    ):
        try:
            Path(
                str(temporary) + suffix
            ).unlink()
        except FileNotFoundError:
            pass

    print(
        "FULL3809_PUBLISH_START "
        f"source={source} "
        f"destination={destination}",
        flush=True,
    )

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
            pages=16384,
            sleep=0.0,
        )

        destination_connection.commit()

    finally:
        destination_connection.close()
        source_connection.close()

    os.replace(
        temporary,
        destination,
    )

    print(
        "FULL3809_PUBLISH_DONE "
        f"bytes={destination.stat().st_size}",
        flush=True,
    )


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: coordinator.py "
            "SHARED_DB LOCAL_DB SPOOL RUN_DIR",
            flush=True,
        )
        return 2

    shared_database = Path(
        sys.argv[1]
    ).resolve()

    local_database = Path(
        sys.argv[2]
    ).resolve()

    spool_root = Path(
        sys.argv[3]
    ).resolve()

    run_dir = Path(
        sys.argv[4]
    ).resolve()

    signal.signal(
        signal.SIGTERM,
        request_stop,
    )

    signal.signal(
        signal.SIGUSR1,
        request_stop,
    )

    signal.signal(
        signal.SIGINT,
        request_stop,
    )

    os.environ[
        "DISTRIBUTED_SPOOL_ROOT"
    ] = str(spool_root)

    db = Database(
        local_database,
        read_only=False,
        command_spool=None,
    )

    spool = DistributedSpool(
        spool_root
    )

    cheap.ensure_import_table(
        db
    )

    cheap.active_db_path = (
        lambda: local_database
    )

    codeql.active_db_path = (
        lambda: local_database
    )

    # Critical for this completion run:
    # do NOT write another complete 35 GB scanner
    # snapshot onto shared NFS.
    cheap.create_snapshot = (
        lambda source, destination: None
    )

    codeql.create_snapshot = (
        lambda source, destination: None
    )

    cheap_restored = (
        reconcile_archived_results(
            db,
            spool,
            "cheap_analysis",
        )
    )

    codeql_restored = (
        reconcile_archived_results(
            db,
            spool,
            "codeql_security",
        )
    )

    print(
        "FULL3809_RECONCILE "
        f"cheap_restored={cheap_restored} "
        f"codeql_restored={codeql_restored}",
        flush=True,
    )

    def cycle(
        do_enqueue: bool,
    ) -> dict:
        values = {
            "cheap_imported": 0,
            "codeql_imported": 0,
            "cheap_requeued": 0,
            "codeql_requeued": 0,
            "cheap_created": 0,
            "codeql_created": 0,
        }

        try:
            values[
                "cheap_imported"
            ] = cheap.import_results(
                db,
                spool,
            )
        except Exception:
            traceback.print_exc()

        try:
            values[
                "codeql_imported"
            ] = codeql.import_results(
                db,
                spool,
            )
        except Exception:
            traceback.print_exc()

        try:
            values[
                "cheap_requeued"
            ] = spool.requeue_stale(
                "cheap_analysis",
                stale_seconds=4 * 60 * 60,
            )
        except Exception:
            traceback.print_exc()

        try:
            values[
                "codeql_requeued"
            ] = spool.requeue_stale(
                "codeql_security",
                stale_seconds=12 * 60 * 60,
            )
        except Exception:
            traceback.print_exc()

        if do_enqueue:
            try:
                values[
                    "cheap_created"
                ] = cheap.enqueue_jobs(
                    db,
                    spool,
                    shared_database,
                )
            except Exception:
                traceback.print_exc()

            try:
                values[
                    "codeql_created"
                ] = codeql.enqueue_jobs(
                    db,
                    spool,
                    shared_database,
                )
            except Exception:
                traceback.print_exc()

        return values

    initial = cycle(
        True
    )

    (
        unfinished,
        errors,
        statuses,
    ) = unfinished_state(
        local_database
    )

    cheap_counts = spool.counts(
        "cheap_analysis"
    )

    codeql_counts = spool.counts(
        "codeql_security"
    )

    ready_payload = {
        "shared_database": str(
            shared_database
        ),
        "local_database": str(
            local_database
        ),
        "spool": str(
            spool_root
        ),
        "unfinished": unfinished,
        "errors": errors,
        "scanner_statuses": statuses,
        "initial_cycle": initial,
        "cheap": cheap_counts,
        "codeql": codeql_counts,
    }

    write_json(
        run_dir
        / "COORDINATOR_READY.json",
        ready_payload,
    )

    print(
        "FULL3809_COORDINATOR_READY "
        f"unfinished={unfinished} "
        f"cheap={cheap_counts} "
        f"codeql={codeql_counts}",
        flush=True,
    )

    quiet_rounds = 0
    last_enqueue = time.monotonic()
    completed = False

    while not STOP:
        now = time.monotonic()

        do_enqueue = (
            now - last_enqueue
            >= 300
        )

        values = cycle(
            do_enqueue
        )

        if do_enqueue:
            last_enqueue = now

        (
            unfinished,
            errors,
            statuses,
        ) = unfinished_state(
            local_database
        )

        cheap_counts = spool.counts(
            "cheap_analysis"
        )

        codeql_counts = spool.counts(
            "codeql_security"
        )

        status_payload = {
            "updated_at": time.time(),
            "unfinished": unfinished,
            "errors": errors,
            "scanner_statuses": statuses,
            "cycle": values,
            "cheap": cheap_counts,
            "codeql": codeql_counts,
        }

        write_json(
            run_dir
            / "status.json",
            status_payload,
        )

        print(
            "FULL3809_STATUS "
            f"unfinished={unfinished} "
            f"errors={errors} "
            f"cheap={cheap_counts} "
            f"codeql={codeql_counts} "
            f"cycle={values}",
            flush=True,
        )

        if (
            unfinished == 0
            and queue_active(
                cheap_counts
            ) == 0
            and queue_active(
                codeql_counts
            ) == 0
        ):
            quiet_rounds += 1
        else:
            quiet_rounds = 0

        if quiet_rounds >= 3:
            completed = True
            break

        time.sleep(5)

    for _ in range(5):
        imported = 0

        try:
            imported += int(
                cheap.import_results(
                    db,
                    spool,
                )
                or 0
            )
        except Exception:
            traceback.print_exc()

        try:
            imported += int(
                codeql.import_results(
                    db,
                    spool,
                )
                or 0
            )
        except Exception:
            traceback.print_exc()

        if imported == 0:
            break

        time.sleep(1)

    (
        unfinished,
        errors,
        statuses,
    ) = unfinished_state(
        local_database
    )

    cheap_counts = spool.counts(
        "cheap_analysis"
    )

    codeql_counts = spool.counts(
        "codeql_security"
    )

    publish_database(
        local_database,
        shared_database,
    )

    final_payload = {
        "completed_pending_zero": bool(
            completed
            and unfinished == 0
            and queue_active(
                cheap_counts
            ) == 0
            and queue_active(
                codeql_counts
            ) == 0
        ),
        "unfinished": unfinished,
        "errors": errors,
        "scanner_statuses": statuses,
        "cheap": cheap_counts,
        "codeql": codeql_counts,
        "shared_database": str(
            shared_database
        ),
    }

    write_json(
        run_dir
        / "FINAL_STATUS.json",
        final_payload,
    )

    print(
        "FULL3809_FINAL "
        f"completed_pending_zero="
        f"{final_payload['completed_pending_zero']} "
        f"unfinished={unfinished} "
        f"errors={errors}",
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
