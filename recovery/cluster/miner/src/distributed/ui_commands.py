from __future__ import annotations

import os
from pathlib import Path

from src.db.database import Database
from src.distributed.spool import DistributedSpool

POOL = "ui_commands"


def _archive_result(spool: DistributedSpool, task_id: str) -> None:
    result = spool.queue_path(POOL, "results") / f"{task_id}.json"
    archive = spool.queue_path(POOL, "results") / "imported"
    archive.mkdir(parents=True, exist_ok=True)
    if result.exists():
        os.replace(result, archive / result.name)


def process_commands(
    db: Database,
    spool: DistributedSpool,
    *,
    limit: int = 200,
) -> int:
    processed = 0
    worker_id = "coordinator-ui-commands"

    for _ in range(max(1, limit)):
        claim = spool.claim(POOL, worker_id)
        if claim is None:
            break

        payload = dict(claim.payload.get("payload") or {})
        sql = str(payload.get("sql") or "").strip()
        params = tuple(payload.get("params") or ())
        verb = sql.split(None, 1)[0].upper() if sql else ""

        if verb not in {"INSERT", "UPDATE", "DELETE"}:
            spool.publish_failure(
                claim,
                f"Unsupported UI SQL verb: {verb or 'empty'}",
            )
            continue

        try:
            db.execute(sql, params)
            spool.publish_result(
                claim,
                {
                    "status": "ok",
                    "verb": verb,
                },
            )
            _archive_result(spool, claim.task_id)
            processed += 1
        except Exception as exc:
            spool.publish_failure(claim, str(exc))

    return processed
