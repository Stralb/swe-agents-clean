"""True archived Trivy base/head Git worktree execution against a local fake CLI."""
from __future__ import annotations

import json
import socket
import subprocess
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import ArchivedFixtureWorker, FixtureWorkerSettings
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_trivy_local_process import (
    LocalTrivyReplay, REPO_URL, FILENAME, DIFF, ADVISORY_ID,
)


class TrivyOriginalLocalProcessTests(unittest.TestCase):
    def test_full_original_clone_two_git_worktrees_cli_json_and_delta(self):
        with LocalTrivyReplay() as replay:
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual((base["status"], head["status"], summary["status"]),
                             ("ok", "ok", "ok"), (summary, base, head))
            self.assertEqual(len(findings), 1, findings)
            finding = findings[0]
            self.assertEqual((finding["file"], finding["package"], finding["vuln_id"]),
                             (FILENAME, "synthetic-lib", ADVISORY_ID))
            self.assertEqual((finding["introduced"], finding["diff_linked"]), (1, True))
            self.assertEqual(finding["line"], 1)
            self.assertEqual(finding["evidence"]["pr_attributable"], True)
            counts = json.loads(summary["stdout"])
            self.assertEqual(
                (counts["base_findings"], counts["head_findings"], counts["introduced"]),
                (0, 1, 1)
            )
            self.assertEqual(
                [call[0] for call in replay.calls],
                ["trivy", "git", "git", "git", "git", "git", "trivy", "trivy"],
            )

    def test_original_trivy_rejects_success_rc_with_malformed_json(self):
        """Original Trivy marks a malformed JSON response as parse_failed."""
        import os
        with LocalTrivyReplay() as replay:
            with mock.patch.dict(os.environ, {"ARNO_TRIVY_FAKE_MODE": "head-malformed-json"}):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual(findings, [])
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "parse_failed", "parse_failed"),
            )

    def test_original_trivy_ignores_nonzero_exit_when_valid_json_present(self):
        """Historical status can be ok despite a failing scanner exit code."""
        import os
        with LocalTrivyReplay() as replay:
            with mock.patch.dict(os.environ, {"ARNO_TRIVY_FAKE_MODE": "head-structured-nonzero"}):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual(len(findings), 1)
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "ok", "ok"),
            )
            self.assertIn("Synthetic Trivy nonzero exit", head["stderr"])

    def test_rejects_nonfixture_repo_or_nonmatching_head_before_commands(self):
        with LocalTrivyReplay() as replay:
            for url, head in [
                ("https://github.com/company/proprietary", replay.head_sha),
                (REPO_URL, "not-fixture-head"),
            ]:
                with self.subTest(url=url, head=head):
                    with self.assertRaises(ValueError):
                        replay.scan(url, replay.base_sha, head, replay.files())
            self.assertEqual(replay.calls, [])

    def test_rejects_unexpected_dependency_file_before_commands(self):
        with LocalTrivyReplay() as replay:
            with self.assertRaises(ValueError):
                replay.scan(REPO_URL, replay.base_sha, replay.head_sha, [{
                    "filename": "../real/requirements.txt", "patch": DIFF,
                }])
            self.assertEqual(replay.calls, [])

    def test_full_original_worker_persists_trivy_snapshot_and_finding(self):
        with LocalTrivyReplay() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/trivy-snapshots", "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 19, "html_url": REPO_URL + "/pull/19",
                "base": {"sha": replay.base_sha, "ref": "main"},
                "head": {"sha": replay.head_sha, "ref": "synthetic"},
            })
            issue = db.upsert_issue(repo, {
                "number": 11, "html_url": REPO_URL + "/issues/11",
                "title": "Synthetic dependency regression",
                "body": "Only test fixture data", "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "synthetic")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class RestrictedBackend(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.trivy_count = 0

                def scan_dependency_snapshots_with_trivy(
                    self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
                ):
                    normalized = [
                        {key: row[key] for key in (
                            "filename", "category", "status", "patch",
                            "additions", "deletions",
                        )}
                        for row in files
                    ]
                    self.trivy_count += 1
                    return replay.scan(repo_url, base_sha, head_sha, normalized,
                                       timeout_seconds=timeout_seconds)

            queue = load_original_queue(db)
            self.assertEqual(queue["seed_scanner_jobs"](db), 6)
            claimed = queue["claim_job"](
                db, ["trivy_dependency"], worker_id="synthetic-local-trivy",
            )
            backend = RestrictedBackend()
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
                ArchivedFixtureWorker(db, backend).run(claimed, FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False, "semgrep": False, "codeql": False,
                    },
                    "cache": {"force_rescan": False},
                }))
            self.assertEqual(backend.trivy_count, 1)
            self.assertEqual(
                db.one("SELECT status FROM scanner_jobs WHERE id=?", (claimed.id,))["status"],
                "ok",
            )
            runs = db.query(
                "SELECT scanner,status FROM scanner_runs WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual([row["scanner"] for row in runs], [
                "trivy-base", "trivy-head", "trivy-scanner",
            ])
            self.assertEqual([row["status"] for row in runs], ["ok", "ok", "ok"])
            finding = db.one(
                "SELECT scanner,finding_type,introduced,rule_id,evidence "
                "FROM scanner_findings WHERE case_id=?",
                (case_id,),
            )
            self.assertEqual(
                (finding["scanner"], finding["finding_type"],
                 finding["introduced"], finding["rule_id"]),
                ("trivy-scanner", "dependency", 1, ADVISORY_ID),
            )
            self.assertIn("pr_attributable", finding["evidence"])
            self.assertEqual(
                db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
