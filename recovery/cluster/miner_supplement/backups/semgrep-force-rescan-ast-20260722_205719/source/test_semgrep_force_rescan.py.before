from __future__ import annotations

import copy
import unittest

from src.workers.job_queue import (
    _scanner_config_for_job,
)


class SemgrepForceRescanTests(
    unittest.TestCase
):
    def test_semgrep_source_forces_real_rescan(
        self,
    ) -> None:
        original = {
            "cache": {
                "force_rescan": False,
            },
            "scanners": {
                "semgrep": False,
                "gitleaks": False,
                "codeql": False,
            },
        }

        before = copy.deepcopy(
            original
        )

        configured = _scanner_config_for_job(
            original,
            "semgrep_source",
        )

        self.assertTrue(
            configured[
                "scanners"
            ][
                "semgrep"
            ]
        )

        self.assertTrue(
            configured[
                "cache"
            ][
                "force_rescan"
            ]
        )

        self.assertEqual(
            original,
            before,
            "Input configuration was mutated",
        )

    def test_unrelated_job_does_not_force_rescan(
        self,
    ) -> None:
        original = {
            "cache": {
                "force_rescan": False,
            },
            "scanners": {
                "semgrep": False,
                "gitleaks": False,
                "codeql": False,
            },
        }

        configured = _scanner_config_for_job(
            original,
            "dependency_downgrade",
        )

        self.assertFalse(
            bool(
                configured.get(
                    "cache",
                    {},
                ).get(
                    "force_rescan"
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
