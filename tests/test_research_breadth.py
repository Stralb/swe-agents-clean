from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ui.views.research_coverage import (
    load_research_coverage,
)


class ResearchBreadthTests(
    unittest.TestCase
):
    def test_repository_depths_are_separate(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            database = root / "test.db"
            spool = root / "spool"

            spool.mkdir()

            connection = sqlite3.connect(
                database
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
                    (
                        "gamma/three",
                        30,
                        31,
                    ),
                    (
                        "delta/four",
                        None,
                        None,
                    ),
                    (
                        "epsilon/five",
                        -1,
                        -1,
                    ),
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
                        "completed",
                        "repo:alpha/one is:pr",
                    ),
                    (
                        "repo_window",
                        "running",
                        "repo:beta/two is:pr",
                    ),
                ],
            )

            connection.commit()
            connection.close()

            summary = load_research_coverage(
                str(database),
                spool,
            )

            self.assertEqual(
                summary[
                    "repositories_reached"
                ],
                5,
            )

            self.assertEqual(
                summary[
                    "candidate_repositories"
                ],
                3,
            )

            self.assertEqual(
                summary[
                    "completed_repository_scans"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "candidates_assessed"
                ],
                3,
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
