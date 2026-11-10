from __future__ import annotations

import unittest

from ui.views.case_review import (
    ROUTE_TO_SCANNER,
)
from ui.views.scanner_progress import (
    CHEAP_SCANNERS,
    TRACKED_SCANNERS,
    _scan_progress_data,
)


class RecordingDatabase:
    def __init__(
        self,
    ) -> None:
        self.queries: list[str] = []

    def query(
        self,
        query: str,
        parameters: tuple = (),
    ) -> list[dict]:
        self.queries.append(
            query
        )

        if (
            "SELECT id FROM cases"
            in query
        ):
            return [
                {
                    "id": 1,
                }
            ]

        if "FROM scanner_runs sr" in query:
            return [
                {
                    "case_id": 1,
                    "scanner": "gitleaks",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                },
                {
                    "case_id": 1,
                    "scanner": "dependency-diff",
                    "status": "not_applicable",
                    "started_at": None,
                    "finished_at": None,
                },
                {
                    "case_id": 1,
                    "scanner": "osv-scanner",
                    "status": "not_applicable",
                    "started_at": None,
                    "finished_at": None,
                },
                {
                    "case_id": 1,
                    "scanner": "semgrep",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                },
                {
                    "case_id": 1,
                    "scanner": "trivy-scanner",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                },
                {
                    "case_id": 1,
                    "scanner": "codeql",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                },
            ]

        return []

    def one(
        self,
        query: str,
        parameters: tuple = (),
    ) -> dict:
        self.queries.append(
            query
        )

        lowered = query.lower()

        if (
            "count" in lowered
            or "sum(" in lowered
            or "max(" in lowered
            or "min(" in lowered
        ):
            return {
                "n": 0,
                "count": 0,
                "jobs": 0,
                "errors": 0,
                "total": 0,
                "value": 0,
            }

        return {}


class TrivyUiMappingTests(
    unittest.TestCase
):
    def test_trivy_is_tracked_as_a_cheap_scanner(
        self,
    ) -> None:
        self.assertIn(
            "trivy-scanner",
            CHEAP_SCANNERS,
        )

        self.assertIn(
            "trivy-scanner",
            TRACKED_SCANNERS,
        )

    def test_actual_trivy_route_maps_to_stored_scanner_name(
        self,
    ) -> None:
        self.assertEqual(
            ROUTE_TO_SCANNER[
                "trivy_dependency"
            ],
            "trivy-scanner",
        )

        for legacy_route in (
            "trivy",
            "trivy_vuln",
            "trivy_secret",
            "trivy_misconfig",
        ):
            self.assertEqual(
                ROUTE_TO_SCANNER[
                    legacy_route
                ],
                "trivy-scanner",
            )

    def test_progress_query_and_coverage_include_trivy(
        self,
    ) -> None:
        database = RecordingDatabase()

        summary, dataframe = (
            _scan_progress_data(
                database
            )
        )

        run_query = next(
            query
            for query in database.queries
            if "FROM scanner_runs sr" in query
        )

        self.assertIn(
            "'trivy-scanner'",
            run_query,
        )

        self.assertEqual(
            summary[
                "cheap_finished"
            ],
            1,
        )

        trivy_rows = dataframe[
            dataframe[
                "Scanner"
            ]
            == "trivy-scanner"
        ]

        self.assertEqual(
            len(
                trivy_rows
            ),
            1,
        )

        self.assertEqual(
            trivy_rows.iloc[0][
                "Finished"
            ],
            "1/1",
        )


if __name__ == "__main__":
    unittest.main()
