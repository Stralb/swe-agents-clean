from __future__ import annotations

import argparse
import time

from src.db.database import Database
from src.distributed.cheap_pipeline import (
    active_db_path,
    enqueue_jobs as enqueue_cheap,
    ensure_import_table,
    import_results as import_cheap,
    spool_root,
)
from src.distributed.codeql_pipeline import (
    enqueue_jobs as enqueue_codeql,
    import_results as import_codeql,
)
from src.distributed.spool import DistributedSpool


def run(*, once: bool, interval: int) -> None:
    db = Database(active_db_path())
    root = spool_root()
    spool = DistributedSpool(root)

    ensure_import_table(db)

    cheap_snapshot = (
        root / "snapshots" / "cheap-analysis.db"
    )

    codeql_snapshot = (
        root / "snapshots" / "codeql-security.db"
    )

    while True:
        cheap_imported = import_cheap(db, spool)
        codeql_imported = import_codeql(db, spool)

        cheap_requeued = spool.requeue_stale(
            "cheap_analysis",
            stale_seconds=4 * 60 * 60,
        )

        codeql_requeued = spool.requeue_stale(
            "codeql_security",
            stale_seconds=12 * 60 * 60,
        )

        cheap_created = enqueue_cheap(
            db,
            spool,
            cheap_snapshot,
        )

        codeql_created = enqueue_codeql(
            db,
            spool,
            codeql_snapshot,
        )

        cheap_counts = spool.counts(
            "cheap_analysis"
        )

        codeql_counts = spool.counts(
            "codeql_security"
        )

        print(
            f"coordinator "
            f"cheap_imported={cheap_imported} "
            f"codeql_imported={codeql_imported} "
            f"cheap_created={cheap_created} "
            f"codeql_created={codeql_created} "
            f"cheap_requeued={cheap_requeued} "
            f"codeql_requeued={codeql_requeued} "
            f"cheap={cheap_counts} "
            f"codeql={codeql_counts}",
            flush=True,
        )

        if once:
            return

        time.sleep(max(2, interval))


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

    run(
        once=args.once,
        interval=args.interval,
    )


if __name__ == "__main__":
    main()
