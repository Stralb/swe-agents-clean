from __future__ import annotations

import sqlite3
from pathlib import Path


def load_existing_repo_seed_names(
    database_path: str | Path,
) -> list[str]:
    """Read repository names from an existing miner database."""

    path = Path(database_path).expanduser()

    if not path.is_absolute():
        project_root = Path(__file__).resolve().parents[2]
        path = (project_root / path).resolve()

    if not path.exists():
        return []

    names: set[str] = set()

    connection = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
        timeout=10,
    )

    try:
        connection.execute("PRAGMA query_only = ON")

        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = ?
                """,
                ("table",),
            )
        }

        candidates = (
            (
                "repos",
                (
                    "full_name",
                    "repo",
                    "repository",
                    "repo_full_name",
                    "name_with_owner",
                ),
            ),
            (
                "cases",
                (
                    "repo",
                    "repository",
                    "repo_full_name",
                    "full_name",
                ),
            ),
            (
                "pull_requests",
                (
                    "repo",
                    "repository",
                    "repo_full_name",
                    "full_name",
                ),
            ),
            (
                "issues",
                (
                    "repo",
                    "repository",
                    "repo_full_name",
                    "full_name",
                ),
            ),
        )

        for table_name, possible_columns in candidates:
            if table_name not in tables:
                continue

            columns = {
                row[1]
                for row in connection.execute(
                    f'PRAGMA table_info("{table_name}")'
                )
            }

            selected = next(
                (
                    column
                    for column in possible_columns
                    if column in columns
                ),
                None,
            )

            if selected is not None:
                rows = connection.execute(
                    (
                        f'SELECT DISTINCT "{selected}" '
                        f'FROM "{table_name}" '
                        f'WHERE "{selected}" IS NOT NULL'
                    )
                ).fetchall()

                for row in rows:
                    value = str(row[0] or "").strip()

                    if (
                        value.count("/") == 1
                        and not value.startswith("/")
                        and not value.endswith("/")
                    ):
                        names.add(value)

            elif (
                table_name == "repos"
                and "owner" in columns
                and "name" in columns
            ):
                rows = connection.execute(
                    """
                    SELECT DISTINCT owner, name
                    FROM repos
                    WHERE owner IS NOT NULL
                      AND name IS NOT NULL
                    """
                ).fetchall()

                for owner, name in rows:
                    value = (
                        str(owner or "").strip()
                        + "/"
                        + str(name or "").strip()
                    )

                    if (
                        value.count("/") == 1
                        and not value.startswith("/")
                        and not value.endswith("/")
                    ):
                        names.add(value)

    finally:
        connection.close()

    return sorted(
        names,
        key=str.lower,
    )
