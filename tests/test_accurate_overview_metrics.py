from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ui.views.overview import (
    _mining_scope_summary,
)


class AccurateOverviewMetricsTests(
    unittest.TestCase
):
    def test_metrics_are_deduplicated(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "test.db"

            connection = sqlite3.connect(
                path
            )

            connection.executescript(
                """
                CREATE TABLE repos (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT
                );

                CREATE TABLE issues (
                    id INTEGER PRIMARY KEY,
                    repo_id INTEGER,
                    number INTEGER
                );

                CREATE TABLE pull_requests (
                    id INTEGER PRIMARY KEY,
                    repo_id INTEGER,
                    number INTEGER
                );

                CREATE TABLE cases (
                    id INTEGER PRIMARY KEY,
                    repo_id INTEGER,
                    issue_id INTEGER,
                    pr_id INTEGER
                );

                CREATE TABLE excluded_cases (
                    repo TEXT,
                    issue_number INTEGER,
                    pr_number INTEGER
                );

                CREATE TABLE retrieval_queries (
                    stream_key TEXT,
                    status TEXT,
                    final_query TEXT
                );
                """
            )

            connection.executemany(
                """
                INSERT INTO repos(
                    id,
                    full_name
                )
                VALUES (?, ?)
                """,
                [
                    (1, "alpha/one"),
                    (2, "beta/two"),
                ],
            )

            connection.executemany(
                """
                INSERT INTO issues(
                    id,
                    repo_id,
                    number
                )
                VALUES (?, ?, ?)
                """,
                [
                    (1, 1, 10),
                    (2, 2, 20),
                ],
            )

            connection.executemany(
                """
                INSERT INTO pull_requests(
                    id,
                    repo_id,
                    number
                )
                VALUES (?, ?, ?)
                """,
                [
                    (1, 1, 11),
                    (2, 2, 21),
                ],
            )

            connection.executemany(
                """
                INSERT INTO cases(
                    id,
                    repo_id,
                    issue_id,
                    pr_id
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (1, 1, 1, 1),
                    (2, 2, 2, 2),
                ],
            )

            connection.executemany(
                """
                INSERT INTO excluded_cases(
                    repo,
                    issue_number,
                    pr_number
                )
                VALUES (?, ?, ?)
                """,
                [
                    ("alpha/one", 10, 11),
                    ("gamma/three", 30, 31),
                    ("gamma/three", 30, 31),
                ],
            )

            connection.executemany(
                """
                INSERT INTO retrieval_queries(
                    stream_key,
                    status,
                    final_query
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        "repo_window",
                        "ok",
                        (
                            "repo:alpha/one "
                            "is:pr is:merged"
                        ),
                    ),
                    (
                        "repo_window",
                        "ok",
                        (
                            "repo:alpha/one "
                            "is:pr is:merged"
                        ),
                    ),
                    (
                        "repo_window",
                        "running",
                        (
                            "repo:beta/two "
                            "is:pr is:merged"
                        ),
                    ),
                    (
                        "repo_window",
                        "completed",
                        (
                            "repo:gamma/three "
                            "is:pr is:merged"
                        ),
                    ),
                ],
            )

            connection.commit()
            connection.close()

            summary = _mining_scope_summary(
                str(path),
                path.stat().st_mtime_ns,
            )

            self.assertEqual(
                summary[
                    "repositories_scanned"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "included_cases"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "excluded_cases"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "cases_touched"
                ],
                3,
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
