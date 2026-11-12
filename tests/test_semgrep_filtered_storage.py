from __future__ import annotations

import json
import unittest
from typing import Any

from miner.scanners.scanner_runner import (
    _insert_finding,
)
from miner.scanners.semgrep_scanner import (
    classify_semgrep_to_pr_delta,
    filter_semgrep_to_pr_delta,
)


class RecordingDatabase:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            tuple[
                str,
                tuple[Any, ...],
            ]
        ] = []

    def execute(
        self,
        query: str,
        params: tuple[Any, ...],
    ) -> None:
        self.calls.append(
            (
                query,
                params,
            )
        )


class SemgrepFilteredEvidenceTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        self.files = [
            {
                "filename": "src/app.js",
                "patch": (
                    "@@ -0,0 +1,2 @@\n"
                    "+const input = process.argv[2];\n"
                    "+runCommand(input);\n"
                ),
            }
        ]

    def test_low_confidence_audit_is_retained_but_not_introduced(
        self,
    ) -> None:
        findings = [
            {
                "file": "src/app.js",
                "line": 2,
                "rule": "detect-child-process",
                "severity": "error",
                "confidence": "LOW",
                "likelihood": "LOW",
                "impact": "HIGH",
                "subcategory": [
                    "audit",
                ],
                "description": (
                    "Possible command injection"
                ),
                "raw": {
                    "check_id": (
                        "detect-child-process"
                    ),
                },
            }
        ]

        classified = (
            classify_semgrep_to_pr_delta(
                findings,
                self.files,
            )
        )

        self.assertEqual(
            len(
                classified
            ),
            1,
        )

        finding = classified[0]

        self.assertTrue(
            finding[
                "diff_linked"
            ]
        )

        self.assertFalse(
            finding[
                "promoted"
            ]
        )

        self.assertEqual(
            finding[
                "introduced"
            ],
            0,
        )

        self.assertEqual(
            finding[
                "finding_type"
            ],
            "semgrep_filtered",
        )

        self.assertEqual(
            finding[
                "rejection_reasons"
            ],
            [
                "low_confidence_audit",
            ],
        )

        evidence = json.loads(
            finding[
                "evidence"
            ]
        )

        self.assertFalse(
            evidence[
                "promoted"
            ]
        )

        self.assertEqual(
            filter_semgrep_to_pr_delta(
                findings,
                self.files,
            ),
            [],
        )

    def test_strong_finding_remains_introduced_vulnerability(
        self,
    ) -> None:
        findings = [
            {
                "file": "src/app.js",
                "line": 2,
                "rule": "dangerous-command",
                "severity": "error",
                "confidence": "HIGH",
                "likelihood": "HIGH",
                "impact": "HIGH",
                "subcategory": [
                    "security",
                ],
                "description": (
                    "Confirmed dangerous command"
                ),
            }
        ]

        classified = (
            classify_semgrep_to_pr_delta(
                findings,
                self.files,
            )
        )

        self.assertEqual(
            len(
                classified
            ),
            1,
        )

        finding = classified[0]

        self.assertTrue(
            finding[
                "promoted"
            ]
        )

        self.assertEqual(
            finding[
                "introduced"
            ],
            1,
        )

        self.assertEqual(
            finding[
                "finding_type"
            ],
            "vulnerability",
        )

        promoted = (
            filter_semgrep_to_pr_delta(
                findings,
                self.files,
            )
        )

        self.assertEqual(
            len(
                promoted
            ),
            1,
        )

    def test_insert_finding_respects_introduced_zero(
        self,
    ) -> None:
        database = RecordingDatabase()

        finding = {
            "file": "src/app.js",
            "line": 2,
            "rule": "detect-child-process",
            "severity": "error",
            "description": (
                "Possible command injection"
            ),
            "introduced": 0,
            "promoted": False,
            "finding_type": (
                "semgrep_filtered"
            ),
            "evidence": json.dumps(
                {
                    "promoted": False,
                    "rejection_reasons": [
                        "low_confidence_audit",
                    ],
                }
            ),
        }

        _insert_finding(
            database,
            1,
            2,
            "semgrep",
            "semgrep_filtered",
            finding,
        )

        self.assertEqual(
            len(
                database.calls
            ),
            1,
        )

        _, params = (
            database.calls[0]
        )

        self.assertEqual(
            params[3],
            "semgrep_filtered",
        )

        self.assertEqual(
            params[-1],
            0,
        )


if __name__ == "__main__":
    unittest.main()
