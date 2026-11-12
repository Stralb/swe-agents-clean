from __future__ import annotations

import os
import sqlite3
from pathlib import Path


root = Path(__file__).resolve().parents[1]
schema_path = root / "src" / "db" / "schema.sql"

raw_db_path = os.environ.get("DB_PATH")
if not raw_db_path:
    raise RuntimeError("DB_PATH is not set")

db_path = Path(raw_db_path).expanduser()
db_path.parent.mkdir(parents=True, exist_ok=True)

if not schema_path.exists():
    raise FileNotFoundError(f"Schema not found: {schema_path}")

schema_sql = schema_path.read_text(encoding="utf-8")

connection = sqlite3.connect(db_path)

try:
    connection.executescript(schema_sql)
    connection.commit()

    required_tables = {
        "repos",
        "issues",
        "pull_requests",
        "cases",
        "ai_markers",
        "excluded_cases",
        "retrieval_queries",
    }

    present_tables = {
        row[0]
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    missing = required_tables - present_tables
    if missing:
        raise RuntimeError(
            "Database schema initialization incomplete; missing: "
            + ", ".join(sorted(missing))
        )

    print(f"Initialized database: {db_path}")
    print(f"Tables present: {len(present_tables)}")
finally:
    connection.close()
