from __future__ import annotations

import argparse
import time

from src.db.database import Database
from src.distributed.cheap_pipeline import (
    active_db_path,
    ensure_import_table,
    import_results,
    spool_root,
)
from src.distributed.spool import DistributedSpool


def run(*, once: bool, interval: int) -> None:
    db = Database(active_db_path())
    spool = DistributedSpool(spool_root())

    ensure_import_table(db)

    while True:
        imported = import_results(db, spool)
        counts = spool.counts("cheap_analysis")


        print(
            f"importer imported={imported} counts={counts}",
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
