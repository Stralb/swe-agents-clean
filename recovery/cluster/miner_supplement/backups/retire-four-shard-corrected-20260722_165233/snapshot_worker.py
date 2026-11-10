import json
import os
import sqlite3
import uuid
from pathlib import Path

pid = os.environ["TARGET_PID"]
destination = Path(os.environ["TARGET_ARTIFACT"])

database_paths = set()

for descriptor in Path(f"/proc/{pid}/fd").glob("*"):
    try:
        target = os.readlink(descriptor)
    except Exception:
        continue

    target = target.replace(" (deleted)", "")

    for suffix in ("-wal", "-shm", "-journal"):
        if target.endswith(suffix):
            target = target[:-len(suffix)]

    if target.endswith((".db", ".sqlite", ".sqlite3")):
        database_paths.add(target)

candidates = [
    Path(path)
    for path in database_paths
    if Path(path).name == "mining.db"
]

if len(candidates) != 1:
    raise RuntimeError(
        "Expected one open mining.db; found "
        + repr(candidates)
    )

source_path = candidates[0]

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

source = sqlite3.connect(
    f"file:{source_path}?mode=ro",
    uri=True,
    timeout=120,
)

target = sqlite3.connect(
    str(temporary),
    timeout=120,
)

try:
    source.execute("PRAGMA busy_timeout=120000")
    target.execute("PRAGMA busy_timeout=120000")

    source.backup(
        target,
        pages=1000,
        sleep=0.05,
    )

    target.commit()

    check = target.execute(
        "PRAGMA quick_check"
    ).fetchone()[0]

    if check != "ok":
        raise RuntimeError(
            "Snapshot quick_check failed: "
            + str(check)
        )

    tables = {
        row[0]
        for row in target.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            """
        )
    }

    counts = {}

    for table in (
        "repos",
        "pull_requests",
        "issues",
        "cases",
        "excluded_cases",
    ):
        if table in tables:
            counts[table] = target.execute(
                f'SELECT COUNT(*) FROM "{table}"'
            ).fetchone()[0]

finally:
    target.close()
    source.close()

os.replace(temporary, destination)

print(json.dumps({
    "source": str(source_path),
    "artifact": str(destination),
    "counts": counts,
}))
