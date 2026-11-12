from __future__ import annotations

import copy
import unittest

from miner.settings import load_settings
from miner.workers.job_queue import (
    _scanner_config_for_job,
)


class TrivyForceRescanTests(
    unittest.TestCase
):
    def setUp(
        self,
    ) -> None:
        loaded = load_settings()

        self.config = getattr(
            loaded,
            "config",
            loaded,
        )

    def test_trivy_dependency_forces_real_rescan(
        self,
    ) -> None:
        original = copy.deepcopy(
            self.config
        )

        configured = (
            _scanner_config_for_job(
                self.config,
                "trivy_dependency",
            )
        )

        self.assertTrue(
            configured[
                "scanners"
            ][
                "trivy"
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
            self.config,
            original,
        )

    def test_unrelated_job_does_not_force_rescan(
        self,
    ) -> None:
        configured = (
            _scanner_config_for_job(
                self.config,
                "dependency_downgrade",
            )
        )

        self.assertFalse(
            bool(
                configured.get(
                    "cache",
                    {},
                ).get(
                    "force_rescan",
                    False,
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
