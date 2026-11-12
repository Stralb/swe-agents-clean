from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


COMPLETED_STATUSES = {
    "ok",
    "complete",
    "completed",
    "success",
    "succeeded",
}

REPOSITORY_PATTERN = re.compile(
    r"(?:^|\s)repo:([^\s]+)",
    re.IGNORECASE,
)

TASK_PATTERN = re.compile(
    r"^(mining-\d+)-(\d+)-of-(\d+)$"
)


def _tables(
    connection: sqlite3.Connection,
) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }


def _columns(
    connection: sqlite3.Connection,
    table: str,
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f"PRAGMA table_info({table})"
        )
    }


def _repository_key(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip().lower()


def _number_key(
    value: Any,
) -> str:
    text = str(
        value or ""
    ).strip()

    if not text:
        return ""

    try:
        number = int(text)
    except (
        TypeError,
        ValueError,
    ):
        return ""

    if number <= 0:
        return ""

    return str(number)


def _candidate_key(
    repository: Any,
    issue_number: Any,
    pr_number: Any,
) -> tuple[str, str, str] | None:
    repository_value = _repository_key(
        repository
    )

    issue_value = _number_key(
        issue_number
    )

    pr_value = _number_key(
        pr_number
    )

    if not (
        repository_value
        and issue_value
        and pr_value
    ):
        return None

    return (
        repository_value,
        issue_value,
        pr_value,
    )


def _completed_repositories(
    connection: sqlite3.Connection,
) -> set[str]:
    if (
        "retrieval_queries"
        not in _tables(connection)
    ):
        return set()

    columns = _columns(
        connection,
        "retrieval_queries",
    )

    if not {
        "stream_key",
        "status",
    }.issubset(columns):
        return set()

    repository_column = next(
        (
            name
            for name in (
                "repo",
                "repository",
            )
            if name in columns
        ),
        None,
    )

    query_column = next(
        (
            name
            for name in (
                "final_query",
                "query",
            )
            if name in columns
        ),
        None,
    )

    selected = [
        "status",
    ]

    if repository_column:
        selected.append(
            repository_column
        )

    if query_column:
        selected.append(
            query_column
        )

    rows = connection.execute(
        """
        SELECT
            """
        + ", ".join(selected)
        + """
        FROM retrieval_queries
        WHERE LOWER(
            COALESCE(
                stream_key,
                ''
            )
        ) LIKE 'repo_window%'
        """
    ).fetchall()

    repositories: set[str] = set()

    for row in rows:
        values = dict(
            zip(
                selected,
                row,
            )
        )

        status = str(
            values.get("status")
            or ""
        ).strip().lower()

        if status not in COMPLETED_STATUSES:
            continue

        repository = ""

        if repository_column:
            repository = _repository_key(
                values.get(
                    repository_column
                )
            )

        if (
            not repository
            and query_column
        ):
            query_text = str(
                values.get(
                    query_column
                )
                or ""
            )

            match = REPOSITORY_PATTERN.search(
                query_text
            )

            if match:
                repository = _repository_key(
                    match.group(1)
                )

        if repository:
            repositories.add(
                repository
            )

    return repositories


def _task_records(
    spool_root: Path,
) -> list[dict[str, Any]]:
    pool_root = (
        spool_root
        / "mining"
    )

    locations = (
        (
            "pending",
            pool_root / "pending",
        ),
        (
            "claimed",
            pool_root / "claimed",
        ),
        (
            "results",
            pool_root / "results",
        ),
        (
            "imported",
            (
                pool_root
                / "results"
                / "imported"
            ),
        ),
    )

    priority = {
        "pending": 0,
        "claimed": 1,
        "results": 2,
        "imported": 3,
    }

    records: dict[
        str,
        dict[str, Any],
    ] = {}

    for state, directory in locations:
        if not directory.exists():
            continue

        for path in sorted(
            directory.glob("*.json")
        ):
            try:
                envelope = json.loads(
                    path.read_text(
                        encoding="utf-8"
                    )
                )
            except Exception:
                continue

            task_id = str(
                envelope.get("task_id")
                or ""
            ).strip()

            match = TASK_PATTERN.fullmatch(
                task_id
            )

            if match is None:
                continue

            result = envelope.get(
                "result",
                {},
            )

            if not isinstance(
                result,
                dict,
            ):
                result = {}

            artifact_value = str(
                result.get(
                    "artifact_path"
                )
                or ""
            ).strip()

            artifact_path = ""

            if artifact_value:
                candidate = Path(
                    artifact_value
                ).resolve()

                try:
                    candidate.relative_to(
                        spool_root
                    )
                except ValueError:
                    candidate = None

                if (
                    candidate is not None
                    and candidate.is_file()
                ):
                    artifact_path = str(
                        candidate
                    )

            record = {
                "state": state,
                "task_id": task_id,
                "batch_id": match.group(1),
                "shard_index": int(
                    match.group(2)
                ),
                "shard_count": int(
                    match.group(3)
                ),
                "artifact_path": artifact_path,
            }

            previous = records.get(
                task_id
            )

            if (
                previous is None
                or priority[state]
                >= priority[
                    str(previous["state"])
                ]
            ):
                records[task_id] = record

    return list(
        records.values()
    )


def _current_batch_summary(
    spool_root: Path,
) -> dict[str, Any]:
    records = _task_records(
        spool_root
    )

    active = [
        record
        for record in records
        if record["state"]
        in {
            "pending",
            "claimed",
        }
    ]

    source = (
        active
        if active
        else records
    )

    if not source:
        return {
            "current_batch_id": "",
            "current_batch_published_shards": 0,
            "current_batch_total_shards": 0,
            "current_batch_repositories_completed": 0,
        }

    batch_id = max(
        {
            str(record["batch_id"])
            for record in source
        },
        key=lambda value: int(
            value.rsplit(
                "-",
                1,
            )[-1]
        ),
    )

    batch_records = [
        record
        for record in records
        if record["batch_id"]
        == batch_id
    ]

    total_shards = max(
        (
            int(record["shard_count"])
            for record in batch_records
        ),
        default=0,
    )

    published = [
        record
        for record in batch_records
        if (
            record["state"]
            in {
                "results",
                "imported",
            }
            and record["artifact_path"]
        )
    ]

    repositories: set[str] = set()

    for record in published:
        artifact = Path(
            str(
                record["artifact_path"]
            )
        )

        connection = sqlite3.connect(
            "file:"
            + str(artifact)
            + "?mode=ro",
            uri=True,
            timeout=20,
        )

        try:
            repositories.update(
                _completed_repositories(
                    connection
                )
            )
        finally:
            connection.close()

    return {
        "current_batch_id": batch_id,
        "current_batch_published_shards": len(
            {
                int(record["shard_index"])
                for record in published
            }
        ),
        "current_batch_total_shards": (
            total_shards
        ),
        "current_batch_repositories_completed": len(
            repositories
        ),
    }


def load_research_coverage(
    db_path: str,
    spool_root: str | Path,
) -> dict[str, Any]:
    """Return all-time research breadth and candidate outcomes."""

    database = Path(
        db_path
    ).resolve()

    connection = sqlite3.connect(
        "file:"
        + str(database)
        + "?mode=ro",
        uri=True,
        timeout=20,
    )

    included: set[
        tuple[str, str, str]
    ] = set()

    raw_excluded: set[
        tuple[str, str, str]
    ] = set()

    repositories_reached: set[
        str
    ] = set()

    incomplete_exclusion_records = 0

    try:
        tables = _tables(
            connection
        )

        if {
            "cases",
            "repos",
            "issues",
            "pull_requests",
        }.issubset(tables):
            rows = connection.execute(
                """
                SELECT
                    r.full_name,
                    i.number,
                    p.number

                FROM cases AS c

                JOIN repos AS r
                  ON r.id = c.repo_id

                JOIN issues AS i
                  ON i.id = c.issue_id

                JOIN pull_requests AS p
                  ON p.id = c.pr_id
                """
            ).fetchall()

            for repository, issue, pr in rows:
                repository_value = (
                    _repository_key(
                        repository
                    )
                )

                if repository_value:
                    repositories_reached.add(
                        repository_value
                    )

                key = _candidate_key(
                    repository,
                    issue,
                    pr,
                )

                if key is not None:
                    included.add(
                        key
                    )

        if "excluded_cases" in tables:
            columns = _columns(
                connection,
                "excluded_cases",
            )

            if {
                "repo",
                "issue_number",
                "pr_number",
            }.issubset(columns):
                rows = connection.execute(
                    """
                    SELECT
                        repo,
                        issue_number,
                        pr_number
                    FROM excluded_cases
                    """
                ).fetchall()

                for repository, issue, pr in rows:
                    repository_value = (
                        _repository_key(
                            repository
                        )
                    )

                    if repository_value:
                        repositories_reached.add(
                            repository_value
                        )

                    key = _candidate_key(
                        repository,
                        issue,
                        pr,
                    )

                    if key is None:
                        incomplete_exclusion_records += 1
                        continue

                    raw_excluded.add(
                        key
                    )

        completed_repository_scans = (
            _completed_repositories(
                connection
            )
        )

    finally:
        connection.close()

    overlap = (
        included
        & raw_excluded
    )

    excluded = (
        raw_excluded
        - included
    )

    assessed = (
        included
        | raw_excluded
    )

    candidate_repositories = {
        key[0]
        for key in assessed
    }

    return {
        "candidates_assessed": len(
            assessed
        ),
        "included_cases": len(
            included
        ),
        "excluded_candidates": len(
            excluded
        ),

        # Broadest query footprint:
        # any repository recorded by included
        # or exclusion processing.
        "repositories_reached": len(
            repositories_reached
        ),

        # Repositories that produced at least
        # one complete issue–PR candidate key.
        "candidate_repositories": len(
            candidate_repositories
        ),

        # Repositories with an explicitly
        # successful repo-window retrieval.
        "completed_repository_scans": len(
            completed_repository_scans
        ),

        # Backward-compatible alias.
        "repositories_assessed": len(
            completed_repository_scans
        ),

        "candidate_overlap": len(
            overlap
        ),
        "raw_unique_exclusions": len(
            raw_excluded
        ),
        "incomplete_exclusion_records": (
            incomplete_exclusion_records
        ),
        **_current_batch_summary(
            Path(spool_root).resolve()
        ),
    }
