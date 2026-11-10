"""Exact historical OSV snapshot materialization with synthetic fake CLI."""
from __future__ import annotations

import json
import socket
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import ArchivedFixtureWorker, FixtureWorkerSettings
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_osv_local_process import (
    LocalOSVReplay, REPO_URL, MANIFEST, COMPANION, ADVISORY_ID, DIFF,
)


class OriginalOSVLocalProcessTests(unittest.TestCase):
    def test_original_git_snapshots_companions_fake_osv_cli_and_advisory_delta(self):
        with LocalOSVReplay() as replay:
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual(
                (summary["status"], base["status"], head["status"]),
                ("ok", "ok", "ok"), (summary, base, head),
            )
            self.assertEqual(len(findings), 1, findings)
            self.assertEqual(
                (findings[0]["file"], findings[0]["package"], findings[0]["vuln_id"]),
                (MANIFEST, "synthetic_lib", ADVISORY_ID),
            )
            self.assertEqual(findings[0]["change_type"], "introduced_vulnerable_dependency")
            self.assertEqual(findings[0]["diff_linked"], True)
            self.assertEqual(
                findings[0]["advisory_aliases"],
                ["GHSA-SYNTHETIC-0001", ADVISORY_ID],
            )
            for meta in (base, head):
                data = json.loads(meta["stdout"])
                self.assertEqual(data["companion_paths"], [COMPANION])
                self.assertEqual(data["materialized_paths"], [MANIFEST, COMPANION])
                self.assertEqual(data["absent_paths"], [])
                self.assertEqual(data["finding_count"], 0 if meta is base else 1)
            counts = json.loads(summary["stdout"])
            self.assertEqual(
                (counts["base_findings"], counts["head_findings"], counts["introduced"]),
                (0, 1, 1),
            )
            self.assertEqual(
                [item[0] for item in replay.calls],
                ["git", "git", "git", "git", "git",
                 "git", "git", "git", "git", "osv-scanner", "osv-scanner"],
            )

    def test_original_osv_treats_invalid_json_with_exit_zero_as_ok(self):
        """Historical OSV can mark malformed JSON as ok when CLI exits zero."""
        import os
        with LocalOSVReplay() as replay:
            with mock.patch.dict(os.environ, {"ARNO_OSV_FAKE_MODE": "head-malformed-success"}):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual(findings, [])
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "ok", "ok"),
            )
            self.assertIn("not valid JSON", json.loads(head["stdout"])["osv_stdout"])

    def test_original_osv_reports_parse_failure_but_keeps_structured_findings(self):
        """An OSV parse failure may still return structured findings."""
        import os
        with LocalOSVReplay() as replay:
            with mock.patch.dict(os.environ, {"ARNO_OSV_FAKE_MODE": "head-extraction-failed"}):
                findings, summary, base, head = replay.scan(
                    REPO_URL, replay.base_sha, replay.head_sha, replay.files()
                )
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["vuln_id"], ADVISORY_ID)
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "parse_failed", "parse_failed"),
            )
            self.assertIn("Could not extract", head["stderr"])

    def test_unapproved_repo_commit_or_path_rejected_without_commands(self):
        with LocalOSVReplay() as replay:
            cases = [
                ("https://github.com/company/private", replay.head_sha, replay.files()),
                (REPO_URL, "bad-head-sha", replay.files()),
                (REPO_URL, replay.head_sha, [{
                    "filename": "../real/pyproject.toml", "patch": DIFF,
                }]),
            ]
            for url, head, files in cases:
                with self.subTest(url=url, head=head):
                    with self.assertRaises(ValueError):
                        replay.scan(url, replay.base_sha, head, files)
            self.assertEqual(replay.calls, [])

    def test_full_original_worker_persists_osv_scan_and_intro_finding(self):
        with LocalOSVReplay() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/osv-snapshots", "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 8, "html_url": REPO_URL + "/pull/8",
                "base": {"sha": replay.base_sha, "ref": "main"},
                "head": {"sha": replay.head_sha, "ref": "synthetic"},
            })
            issue = db.upsert_issue(repo, {
                "number": 7, "html_url": REPO_URL + "/issues/7",
                "title": "Synthetic manifest change",
                "body": "Synthetic fixture only",
                "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "synthetic")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class RestrictedBackend(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.osv_count = 0

                def scan_dependency_snapshots(
                    self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
                ):
                    data = [{
                        key: row[key] for key in (
                            "filename", "category", "status", "patch",
                            "additions", "deletions",
                        )
                    } for row in files]
                    self.osv_count += 1
                    return replay.scan(repo_url, base_sha, head_sha, data,
                                       timeout_seconds=timeout_seconds)

            queue = load_original_queue(db)
            self.assertEqual(queue["seed_scanner_jobs"](db), 6)
            job = queue["claim_job"](
                db, ["osv_dependency"], worker_id="synthetic-osv-worker",
            )
            backend = RestrictedBackend()
            with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
                ArchivedFixtureWorker(db, backend).run(job, FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False,
                        "semgrep": False, "codeql": False,
                    },
                    "cache": {"force_rescan": False},
                }))
            self.assertEqual(backend.osv_count, 1)
            self.assertEqual(
                db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))["status"],
                "ok",
            )
            runs = db.query(
                "SELECT scanner,status FROM scanner_runs WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual(
                [r["scanner"] for r in runs],
                ["osv-base", "osv-head", "osv-scanner"],
            )
            self.assertEqual([r["status"] for r in runs], ["ok", "ok", "ok"])
            finding = db.one(
                "SELECT scanner,finding_type,introduced,rule_id,raw_json "
                "FROM scanner_findings WHERE case_id=?",
                (case_id,),
            )
            self.assertEqual(
                (finding["scanner"], finding["finding_type"],
                 finding["introduced"], finding["rule_id"]),
                ("osv-scanner", "dependency", 1, ADVISORY_ID),
            )
            self.assertIn("GHSA-SYNTHETIC-0001", finding["raw_json"])
            self.assertEqual(
                db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
