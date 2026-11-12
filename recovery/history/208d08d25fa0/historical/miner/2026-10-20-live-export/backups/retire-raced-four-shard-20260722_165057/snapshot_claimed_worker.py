import json
import os
import sqlite3
import uuid
from pathlib import Path

pid = os.environ["TARGET_PID"]
destination = Path(
    os.environ["TARGET_ARTIFACT"]
)

database_paths = set()

for descriptor in Path(
    f"/proc/{pid}/fd"
).glob("*"):
    try:
        target = os.readlink(descriptor)
    except Exception:
        continue

    target = target.replace(
        " (deleted)",
        "",
    )

    for suffix in (
        "-wal",
        "-shm",
        "-journal",
    ):
        if target.endswith(suffix):
            target = target[:-len(suffix)]

    if target.endswith(
        (".db", ".sqlite", ".sqlite3")
    ):
        database_paths.add(target)

candidates = [
    Path(path)
    for path in database_paths
    if Path(path).name == "mining.db"
]

if len(candidates) != 1:
    print(
        json.dumps({
            "preserved": False,
            "reason": (
                "Expected one mining.db; found "
                + str(candidates)
            ),
        })
    )
    raise SystemExit(0)

source_path = candidates[0]

source = sqlite3.connect(
    f"file:{source_path}?mode=ro",
    uri=True,
    timeout=120,
)

try:
    tables = {
        row[0]
        for row in source.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    case_count = (
        source.execute(
            "SELECT COUNT(*) FROM cases"
        ).fetchone()[0]
        if "cases" in tables
        else 0
    )

    if case_count <= 0:
        print(
            json.dumps({
                "preserved": False,
                "reason": "no_cases",
                "cases": case_count,
            })
        )
        raise SystemExit(0)

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

    target = sqlite3.connect(
        str(temporary),
        timeout=120,
    )

    try:
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
                "quick_check failed: "
                + str(check)
            )
    finally:
        target.close()

    os.replace(
        temporary,
        destination,
    )

    print(
        json.dumps({
            "preserved": True,
            "source": str(source_path),
            "artifact": str(destination),
            "cases": case_count,
        })
    )

finally:
    source.close()
