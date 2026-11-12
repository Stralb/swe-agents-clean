from __future__ import annotations

import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path

from ui.views.research_coverage import (
    load_research_coverage,
)


def function_source(
    source: str,
    name: str,
) -> str:
    tree = ast.parse(
        source
    )

    matches = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == name
    ]

    if len(matches) != 1:
        raise AssertionError(
            f"Expected one {name}"
        )

    node = matches[0]
    lines = source.splitlines()

    return "\n".join(
        lines[
            node.lineno - 1:
            node.end_lineno
        ]
    )


def metric_labels(
    source: str,
    function_name: str,
) -> list[str]:
    tree = ast.parse(
        source
    )

    functions = [
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == function_name
    ]

    if len(functions) != 1:
        raise AssertionError(
            f"Expected one {function_name}"
        )

    labels = []

    for node in ast.walk(
        functions[0]
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if (
            not isinstance(
                node.func,
                ast.Attribute,
            )
            or node.func.attr != "metric"
            or not node.args
        ):
            continue

        first = node.args[0]

        if isinstance(
            first,
            ast.Constant,
        ):
            labels.append(
                str(first.value)
            )

    return labels


class ResearchCoverageTests(
    unittest.TestCase
):
    def test_deduplication_and_invalid_keys(
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
                        "alpha/one",
                        10,
                        11,
                    ),
                    (
                        "gamma/three",
                        30,
                        31,
                    ),
                    (
                        "gamma/three",
                        30,
                        31,
                    ),
                    (
                        "invalid/missing",
                        None,
                        41,
                    ),
                    (
                        "invalid/sentinel",
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
                        "repo_window_pr_search",
                        "ok",
                        "repo:beta/two is:pr",
                    ),
                    (
                        "repo_window",
                        "running",
                        "repo:gamma/three is:pr",
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
                    "candidates_assessed"
                ],
                3,
            )

            self.assertEqual(
                summary[
                    "included_cases"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "excluded_candidates"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "candidate_overlap"
                ],
                1,
            )

            self.assertEqual(
                summary[
                    "repositories_assessed"
                ],
                2,
            )

            self.assertEqual(
                summary[
                    "incomplete_exclusion_records"
                ],
                2,
            )

    def test_only_relevant_ui_metrics_remain(
        self,
    ) -> None:
        source = Path(
            "ui/views/overview_fast.py"
        ).read_text(
            encoding="utf-8"
        )

        kpis = function_source(
            source,
            "_render_kpis",
        )

        self.assertIn(
            '"Candidates assessed"',
            kpis,
        )

        self.assertIn(
            '"Included cases"',
            kpis,
        )

        self.assertIn(
            '"Excluded candidates"',
            kpis,
        )

        self.assertIn(
            '"Repositories assessed"',
            kpis,
        )

        self.assertIn(
            '"Needs review"',
            kpis,
        )

        self.assertIn(
            '"Positive cases"',
            kpis,
        )

        self.assertNotIn(
            '"Reviewed"',
            kpis,
        )

        self.assertNotIn(
            '"Cases in dataset"',
            kpis,
        )

        self.assertNotIn(
            "Scan problems",
            kpis,
        )

        labels = metric_labels(
            source,
            "_case_fragment",
        )

        self.assertIn(
            "Introduced findings",
            labels,
        )

        self.assertNotIn(
            "All",
            labels,
        )

        self.assertNotIn(
            "New",
            labels,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
