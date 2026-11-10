from __future__ import annotations

import unittest

from ui.views.insight_data import (
    normalise_scanner,
    scanner_eligibility,
)


class RecordingDatabase:
    def query(
        self,
        query: str,
        parameters: tuple = (),
    ) -> list[dict]:
        if "FROM artifact_regions" in query:
            return []

        if "FROM scanner_jobs" in query:
            return [
                {
                    "case_id": 1,
                    "job_type": "trivy_dependency",
                }
            ]

        if (
            "id AS case_id"
            in query
            and "FROM cases" in query
        ):
            return [
                {
                    "case_id": 1,
                    "pr_id": 10,
                }
            ]

        if "FROM scanner_runs" in query:
            return [
                {
                    "id": 3,
                    "case_id": 1,
                    "pr_id": 10,
                    "scanner": "trivy-scanner",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                    "stdout": "",
                    "stderr": "",
                },
                {
                    "id": 2,
                    "case_id": 1,
                    "pr_id": 10,
                    "scanner": "trivy-head",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                    "stdout": "",
                    "stderr": "",
                },
                {
                    "id": 1,
                    "case_id": 1,
                    "pr_id": 10,
                    "scanner": "trivy-base",
                    "status": "ok",
                    "started_at": None,
                    "finished_at": None,
                    "stdout": "",
                    "stderr": "",
                },
            ]

        return []


class TrivyInsightCanonicalizationTests(
    unittest.TestCase
):
    def test_stored_trivy_scanner_name_is_canonicalized(
        self,
    ) -> None:
        self.assertEqual(
            normalise_scanner(
                "trivy-scanner"
            ),
            "trivy",
        )

    def test_job_and_run_use_same_canonical_key(
        self,
    ) -> None:
        eligible, routes = scanner_eligibility(
            RecordingDatabase()
        )

        self.assertEqual(
            eligible.get(
                "trivy"
            ),
            {
                1,
            },
        )

        self.assertNotIn(
            "trivy-scanner",
            eligible,
        )

        self.assertEqual(
            routes.get(
                1
            ),
            {
                "trivy",
            },
        )


if __name__ == "__main__":
    unittest.main()
