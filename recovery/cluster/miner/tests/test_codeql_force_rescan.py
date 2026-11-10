from __future__ import annotations

import unittest

from src.scanners.scanner_runner import _clear_scanner
from src.workers.job_queue import _scanner_config_for_job


class RecordingDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(
        self,
        sql: str,
        params: tuple[object, ...] = (),
    ) -> None:
        self.calls.append(
            (
                sql,
                params,
            )
        )


class CodeQLForceRescanTests(
    unittest.TestCase
):
    def test_security_job_forces_rescan_without_mutating_input(
        self,
    ) -> None:
        original = {
            "cache": {
                "force_rescan": False,
            },
            "scanners": {
                "codeql_timeout_seconds": 1800,
            },
        }

        configured = _scanner_config_for_job(
            original,
            "codeql_security",
        )

        self.assertTrue(
            configured["cache"][
                "force_rescan"
            ]
        )

        self.assertFalse(
            original["cache"][
                "force_rescan"
            ]
        )

        self.assertTrue(
            configured["scanners"][
                "codeql"
            ]
        )

        self.assertEqual(
            configured["scanners"][
                "codeql_timeout_seconds"
            ],
            1800,
        )

    def test_non_codeql_job_does_not_force_rescan(
        self,
    ) -> None:
        from src.workers.job_queue import (
            JOB_SCANNERS,
        )

        unrelated_job_type = next(
            job_type
            for job_type in JOB_SCANNERS
            if job_type not in {
                "codeql_security",
                "secret_ci",
            }
        )

        configured = _scanner_config_for_job(
            {
                "cache": {
                    "force_rescan": False,
                },
            },
            unrelated_job_type,
        )

        self.assertFalse(
            configured["cache"][
                "force_rescan"
            ]
        )

    def test_codeql_clear_removes_language_specific_runs(
        self,
    ) -> None:
        database = RecordingDatabase()

        _clear_scanner(
            database,
            718,
            (
                "codeql",
                "codeql-base",
                "codeql-head",
            ),
            (
                "vulnerability",
                "code_quality",
            ),
        )

        statements = "\n".join(
            sql
            for sql, _ in database.calls
        )

        self.assertIn(
            "scanner LIKE 'codeql-%'",
            statements,
        )


if __name__ == "__main__":
    unittest.main()
