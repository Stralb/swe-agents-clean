"""Opt-in genuine Semgrep CLI smoke on a fabricated local Git repository.

Never run in the normal suite. CI verifies the official Semgrep 1.181.0 wheel
checksum before enabling these tests. Only the synthetic local fixture is read.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import unittest

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_semgrep_process import (
    LocalSemgrepReplay, REPO_URL, SOURCE_NAMES,
)

VERSION = "1.181.0"


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_PINNED_SEMGREP") == "1",
    "Requires checksum-verified Semgrep installed by synthetic-only CI workflow",
)
class RealSemgrepSyntheticOnlyTests(unittest.TestCase):
    def setUp(self):
        binary = Path(os.environ["ARNO_SEMGREP_EXECUTABLE"]).resolve()
        self.assertEqual(binary.name, "semgrep")
        self.assertTrue(binary.is_file())
        version = subprocess.run(
            [str(binary), "--version"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        self.assertIn(VERSION, version.stdout + version.stderr)
        self.binary = binary

    @staticmethod
    def _assert_two_findings(findings):
        by_file = {f["file"]: f for f in findings}
        assert set(by_file) == set(SOURCE_NAMES), findings
        promoted = by_file["src/app.py"]
        filtered = by_file["tests/test_fixture.py"]
        assert str(promoted.get("rule", "")).endswith("arno-synthetic-smoke"), findings
        assert promoted["finding_type"] == "vulnerability", findings
        assert promoted["introduced"] == 1 and promoted["diff_linked"], findings
        assert filtered["finding_type"] == "semgrep_filtered", findings
        assert filtered["introduced"] == 0, findings
        assert filtered["rejection_reasons"] == ["test_or_example_path"], findings

    def test_real_semgrep_rule_through_exact_archived_clone_and_diff_filter(self):
        with LocalSemgrepReplay(semgrep_executable=self.binary) as replay:
            findings, meta = replay.scan(
                REPO_URL, replay.head_sha, replay.synthetic_files(),
                timeout_seconds=180,
            )
            self.assertEqual(meta["status"], "ok", meta)
            self.assertIn("all_findings=2", meta["stdout"])
            self.assertIn("promoted=1 filtered=1", meta["stdout"])
            self._assert_two_findings(findings)
            self.assertEqual(
                [call[0] for call in replay.calls],
                ["git", "git", "git", "semgrep"],
            )

    def test_real_semgrep_via_archived_worker_into_disposable_sqlite(self):
        with LocalSemgrepReplay(semgrep_executable=self.binary) as replay:
            with disposable_original_database() as db:
                repo = db.insert_or_get_repo({
                    "full_name": "fixture/local-semgrep",
                    "html_url": REPO_URL,
                })
                pr = db.upsert_pr(repo, {
                    "number": 15, "html_url": REPO_URL + "/pull/15",
                    "head": {"ref": "synthetic", "sha": replay.head_sha},
                    "base": {"ref": "main", "sha": replay.head_sha},
                })
                issue = db.upsert_issue(repo, {
                    "number": 14, "html_url": REPO_URL + "/issues/14",
                    "title": "Local fabricated code review",
                    "body": "Review only synthetic example files",
                    "labels": [],
                }, 5, True)
                db.link_issue_pr(issue, pr, "fixture")
                case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
                db.replace_pr_files(pr, replay.synthetic_files())

                class RestrictedRealProvider(FixtureScannerProviders):
                    def __init__(self):
                        super().__init__()
                        self.invocations = 0

                    def scan_head_with_semgrep(
                        self, repo_url, head_sha, files, *,
                        semgrep_config, timeout_seconds,
                    ):
                        if semgrep_config != str(replay.rule_file):
                            raise AssertionError("Unexpected nonlocal Semgrep rule")
                        normalized_files = [
                            {key: row[key] for key in (
                                "filename", "status", "patch", "additions", "deletions"
                            )}
                            for row in files
                        ]
                        self.invocations += 1
                        return replay.scan(
                            repo_url, head_sha, normalized_files,
                            timeout_seconds=timeout_seconds,
                        )

                queue = load_original_queue(db)
                self.assertEqual(queue["seed_scanner_jobs"](db), 6)
                job = queue["claim_job"](
                    db, ["semgrep_source"], worker_id="semgrep-real-fixture",
                )
                provider = RestrictedRealProvider()
                ArchivedFixtureWorker(db, provider).run(
                    job, FixtureWorkerSettings({
                        "scanners": {
                            "gitleaks": False, "dependency_downgrade": False,
                            "osv": False, "trivy": False, "semgrep": False,
                            "codeql": False,
                            "semgrep_config": str(replay.rule_file),
                            "semgrep_timeout_seconds": 180,
                        },
                        "cache": {"force_rescan": False},
                    }),
                )
                self.assertEqual(provider.invocations, 1)
                self.assertEqual(
                    db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))["status"],
                    "ok",
                )
                scanner_run = db.one(
                    "SELECT scanner,status,stdout FROM scanner_runs WHERE case_id=?",
                    (case_id,),
                )
                self.assertEqual(
                    (scanner_run["scanner"], scanner_run["status"]),
                    ("semgrep", "ok"),
                )
                rows = db.query(
                    "SELECT file_path,finding_type,introduced,rule_id "
                    "FROM scanner_findings WHERE case_id=? ORDER BY file_path",
                    (case_id,),
                )
                self.assertEqual(len(rows), 2, rows)
                by_file = {row["file_path"]: row for row in rows}
                self.assertEqual(
                    (by_file["src/app.py"]["finding_type"],
                     by_file["src/app.py"]["introduced"]),
                    ("vulnerability", 1),
                )
                self.assertEqual(
                    (by_file["tests/test_fixture.py"]["finding_type"],
                     by_file["tests/test_fixture.py"]["introduced"]),
                    ("semgrep_filtered", 0),
                )
                self.assertEqual(
                    db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                    "needs_review",
                )


if __name__ == "__main__":
    unittest.main()
