from __future__ import annotations

import unittest

from src.scanners.codeql_scanner import (
    _codeql_no_source_seen,
    _command_timed_out,
    _no_source_meta,
    _timeout_meta,
)


class CodeQLFailureHandlingTests(
    unittest.TestCase
):
    def test_negative_nine_timeout_contract(
        self,
    ) -> None:
        result = {
            "returncode": -9,
            "timeout": True,
            "timed_out": True,
            "status": "timeout",
            "stdout": "partial output",
            "stderr": (
                "Command timed out after "
                "600 seconds and process "
                "group was killed."
            ),
        }

        self.assertTrue(
            _command_timed_out(
                result
            )
        )

        metadata = _timeout_meta(
            "CodeQL analysis",
            result,
            600,
        )

        self.assertEqual(
            metadata["status"],
            "timeout",
        )

        self.assertIn(
            "timed out",
            metadata["stderr"].lower(),
        )

    def test_legacy_124_timeout_contract(
        self,
    ) -> None:
        self.assertTrue(
            _command_timed_out(
                {
                    "returncode": 124,
                    "stdout": "",
                    "stderr": "timeout",
                }
            )
        )

    def test_codeql_no_source_is_detected(
        self,
    ) -> None:
        result = {
            "returncode": 32,
            "stdout": (
                "Only found JavaScript or "
                "TypeScript files that were "
                "empty or contained syntax errors."
            ),
            "stderr": (
                "CodeQL detected code written in "
                "Python, but not any written in "
                "JavaScript/TypeScript."
            ),
        }

        self.assertTrue(
            _codeql_no_source_seen(
                result
            )
        )

        metadata = _no_source_meta(
            result
        )

        self.assertEqual(
            metadata["status"],
            "no_source",
        )

    def test_other_database_failure_is_not_no_source(
        self,
    ) -> None:
        result = {
            "returncode": 2,
            "stdout": (
                "Gradle BUILD FAILED"
            ),
            "stderr": (
                "A fatal error occurred"
            ),
        }

        self.assertFalse(
            _codeql_no_source_seen(
                result
            )
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2,
    )
