from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ui.views.overview import (
    _mining_scope_summary,
)


class CurrentBatchOverviewTests(
    unittest.TestCase
):
    def test_only_current_batch_artifacts_are_counted(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)

            active_db = (
                root / "active.db"
            )

            connection = sqlite3.connect(
                active_db
            )

            connection.executescript(
                """
                CREATE TABLE repos (
                    id INTEGER PRIMARY KEY,
                    full_name TEXT
                );

                CREATE TABLE retrieval_queries (
                    stream_key TEXT,
                    status TEXT,
                    raw_count INTEGER,
                    unique_count INTEGER,
                    final_query TEXT
                );
                """
            )

            connection.execute(
                """
                INSERT INTO retrieval_queries(
                    stream_key,
                    status,
                    raw_count,
                    unique_count,
                    final_query
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    "existing_repo_seed",
                    "ok",
                    183,
                    183,
                    "seed",
                ),
            )

            connection.commit()
            connection.close()

            spool = (
                root
                / "spool"
            )

            pending = (
                spool
                / "mining"
                / "pending"
            )

            imported = (
                spool
                / "mining"
                / "results"
                / "imported"
            )

            artifacts = (
                spool
                / "mining"
                / "artifacts"
            )

            pending.mkdir(
                parents=True
            )

            imported.mkdir(
                parents=True
            )

            artifacts.mkdir(
                parents=True
            )

            (
                pending
                / "mining-100-1-of-32.json"
            ).write_text(
                json.dumps({
                    "task_id": (
                        "mining-100-1-of-32"
                    ),
                }),
                encoding="utf-8",
            )

            artifact = (
                artifacts
                / "mining-100-0-of-32.db"
            )

            connection = sqlite3.connect(
                artifact
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

            connection.execute(
                """
                INSERT INTO issues(
                    id,
                    repo_id,
                    number
                )
                VALUES (1, 1, 10)
                """
            )

            connection.execute(
                """
                INSERT INTO pull_requests(
                    id,
                    repo_id,
                    number
                )
                VALUES (1, 1, 11)
                """
            )

            connection.execute(
                """
                INSERT INTO cases(
                    id,
                    repo_id,
                    issue_id,
                    pr_id
                )
                VALUES (1, 1, 1, 1)
                """
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
                        "alpha/one",
                        10,
                        11,
                    ),
                    (
                        "beta/two",
                        20,
                        21,
                    ),
                    (
                        "beta/two",
                        20,
                        21,
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
                        "ok",
                        (
                            "repo:alpha/one "
                            "is:pr"
                        ),
                    ),
                    (
                        "repo_window",
                        "completed",
                        (
                            "repo:beta/two "
                            "is:pr"
                        ),
                    ),
                ],
            )

            connection.commit()
            connection.close()

            (
                imported
                / "mining-100-0-of-32.json"
            ).write_text(
                json.dumps({
                    "task_id": (
                        "mining-100-0-of-32"
                    ),
                    "result": {
                        "artifact_path": str(
                            artifact
                        ),
                    },
                }),
                encoding="utf-8",
            )

            with mock.patch.dict(
                os.environ,
                {
                    "MINING_SCOPE_SPOOL_ROOT": str(
                        spool
                    ),
                },
                clear=False,
            ):
                if hasattr(
                    _mining_scope_summary,
                    "clear",
                ):
                    _mining_scope_summary.clear()

                summary = (
                    _mining_scope_summary(
                        str(active_db),
                        active_db.stat().st_mtime_ns,
                    )
                )

            self.assertEqual(
                summary["batch_id"],
                "mining-100",
            )

            self.assertEqual(
                summary[
                    "seed_repositories"
                ],
                183,
            )

            self.assertEqual(
                summary[
                    "repositories_scanned"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "completed_shards"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "total_shards"
                ],
                32,
            )

            self.assertEqual(
                summary[
                    "included_cases"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "excluded_cases"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "cases_touched"
                ],
                2,
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
