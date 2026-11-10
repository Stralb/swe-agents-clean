from __future__ import annotations

import os
from pathlib import Path

from src.db.database import Database
from src.pipeline.case_status import sync_case_statuses
from src.settings import PROJECT_ROOT


def main() -> None:
    db = Database(Path(os.getenv("DB_PATH", PROJECT_ROOT / "data/miner.db")))
    db.init_schema(PROJECT_ROOT / "src/db/schema.sql")
    sync_case_statuses(db)
    print("CASE STATUS SUMMARY")
    for r in db.query("SELECT status, downstream_signal, COUNT(*) AS n FROM cases GROUP BY status, downstream_signal ORDER BY status, downstream_signal"):
        print((r["status"], r["downstream_signal"], r["n"]))
    print("SCANNER JOBS")
    for r in db.query("SELECT job_type,status,COUNT(*) AS n FROM scanner_jobs GROUP BY job_type,status ORDER BY job_type,status"):
        print((r["job_type"], r["status"], r["n"]))


if __name__ == "__main__":
    main()
