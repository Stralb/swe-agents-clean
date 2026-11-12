from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from miner.scanners.gitleaks_scanner import (
    scan_files_with_gitleaks,
)
from miner.workers.job_queue import (
    _scanner_config_for_job,
)


class GitleaksRedactedReportTests(
    unittest.TestCase
):
    @staticmethod
    def _run_with_report(
        files: list[dict[str, object]],
    ) -> tuple[
        list[dict[str, object]],
        dict[str, str],
    ]:
        def fake_run_cmd(
            command: list[str],
            timeout: int,
        ) -> dict[str, object]:
            del timeout

            source_root = Path(
                command[
                    command.index(
                        "--source"
                    )
                    + 1
                ]
            )

            report_path = Path(
                command[
                    command.index(
                        "--report-path"
                    )
                    + 1
                ]
            )

            scanned_file = (
                source_root
                / "config"
                / "token.txt"
            )

            report_path.write_text(
                json.dumps(
                    [
                        {
                            "File": str(
                                scanned_file
                            ),
                            "StartLine": 1,
                            "RuleID": "github-pat",
                            "Description": (
                                "GitHub Personal "
                                "Access Token"
                            ),
                            "Match": "REDACTED",
                            "Secret": "REDACTED",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            return {
                "ok": False,
                "returncode": 1,
                "stdout": "",
                "stderr": (
                    "WRN leaks found: 1"
                ),
            }

        with patch(
            "miner.scanners.gitleaks_scanner."
            "shutil.which",
            return_value="/tmp/gitleaks",
        ), patch(
            "miner.scanners.gitleaks_scanner."
            "run_cmd",
            side_effect=fake_run_cmd,
        ):
            return scan_files_with_gitleaks(
                files
            )

    def test_redacted_report_finding_is_retained(
        self,
    ) -> None:
        findings, meta = self._run_with_report(
            [
                {
                    "filename": (
                        "config/token.txt"
                    ),
                    "patch": (
                        "@@ -0,0 +1 @@\n"
                        "+token = "
                        '"github_pat_'
                        "11AA22BB33CC44DD"
                        '55EE66FF77GG88HH"'
                    ),
                }
            ]
        )

        self.assertEqual(
            meta["status"],
            "ok",
        )

        self.assertEqual(
            len(
                findings
            ),
            1,
        )

        self.assertEqual(
            findings[0]["evidence"],
            "<redacted by gitleaks>",
        )

    def test_source_placeholder_is_filtered(
        self,
    ) -> None:
        findings, meta = self._run_with_report(
            [
                {
                    "filename": (
                        "config/token.txt"
                    ),
                    "patch": (
                        "@@ -0,0 +1 @@\n"
                        "+token = "
                        '"github_pat_'
                        'example_placeholder"'
                    ),
                }
            ]
        )

        self.assertEqual(
            meta["status"],
            "ok",
        )

        self.assertEqual(
            findings,
            [],
        )

    def test_secret_jobs_force_rescan(
        self,
    ) -> None:
        original = {
            "cache": {
                "force_rescan": False,
            },
            "scanners": {
                "gitleaks": True,
            },
        }

        configured = _scanner_config_for_job(
            original,
            "secret_ci",
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
                "gitleaks"
            ]
        )


if __name__ == "__main__":
    unittest.main()
