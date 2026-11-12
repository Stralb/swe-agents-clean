"""Original CodeQL Git/DB/SARIF/worker contracts on fabricated local Git only.

Fake CLI validates original command construction; these tests do not claim
CodeQL engine execution, vulnerability detection or historical parity.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_codeql_attribution_contract import (
    load_original_codeql_attribution,
)
from tests.support.archived_codeql_local_process import (
    LocalCodeQLReplay, REPO_URL, FILENAME, RULE, SUITE, PATCH,
)


def settings():
    return FixtureWorkerSettings({
        "scanners": {
            "gitleaks": False,
            "dependency_downgrade": False,
            "osv": False,
            "trivy": False,
            "semgrep": False,
            "codeql": False,
            "codeql_language": "auto",
            "codeql_timeout_seconds": 120,
            "codeql_trigger": "all_codeql",
        },
        "cache": {"force_rescan": False},
    })


class OriginalCodeQLGitProcessTests(unittest.TestCase):
    def test_exact_original_snapshot_runs_git_create_analyze_and_parses_sarif(self):
        with LocalCodeQLReplay() as replay:
            base, bm = replay.scan(
                REPO_URL, replay.base_sha, language="python",
                build_mode="none", query_suite=SUITE, timeout_seconds=120,
            )
            head, hm = replay.scan(
                REPO_URL, replay.head_sha, language="python",
                build_mode="none", query_suite=SUITE, timeout_seconds=120,
            )
            self.assertEqual((bm["status"], hm["status"]), ("ok", "ok"))
            self.assertEqual(base, [])
            self.assertEqual(len(head), 1, head)
            self.assertEqual(
                (head[0]["file"], head[0]["line"], head[0]["rule"]),
                (FILENAME, 5, RULE),
            )
            self.assertIn("external/cwe/cwe-078", head[0]["cwe"])
            self.assertEqual(
                replay.calls,
                ["git", "git", "git", "codeql", "codeql"] * 2,
            )
            original = load_original_codeql_attribution()
            new_findings = original["diff_findings"](base, head)
            promoted = original["filter_findings_to_pr_delta"](
                new_findings, replay.files(),
            )
            self.assertEqual(len(promoted), 1)
            self.assertTrue(promoted[0]["diff_linked"])

    def test_unapproved_repo_sha_or_config_is_rejected_before_any_command(self):
        with LocalCodeQLReplay() as replay:
            for url, sha, query in (
                ("https://github.com/unapproved/repo", replay.head_sha, SUITE),
                (REPO_URL, "unapproved-head", SUITE),
                (REPO_URL, replay.head_sha, "q/potential-untrusted"),
            ):
                with self.subTest(url=url, sha=sha, query=query):
                    with self.assertRaises(ValueError):
                        replay.scan(
                            url, sha, language="python",
                            build_mode="none", query_suite=query,
                            timeout_seconds=120,
                        )
            self.assertEqual(replay.calls, [])

    def test_original_no_source_failure_is_not_a_clean_snapshot(self):
        with LocalCodeQLReplay() as replay:
            with mock.patch.dict(os.environ, {
                "ARNO_FAKE_CODEQL_MODE": "head-no-source",
            }):
                findings, meta = replay.scan(
                    REPO_URL, replay.head_sha, language="python",
                    build_mode="none", query_suite=SUITE, timeout_seconds=120,
                )
            self.assertEqual(findings, [])
            self.assertEqual(meta["status"], "no_source")
            self.assertIn("No source code was seen", meta["stderr"])

    def test_original_ok_status_can_mask_malformed_sarif(self):
        """Reproduce fail-open original status; do not count as clean evidence."""
        with LocalCodeQLReplay() as replay:
            with mock.patch.dict(os.environ, {
                "ARNO_FAKE_CODEQL_MODE": "head-malformed-sarif",
            }):
                findings, metadata = replay.scan(
                    REPO_URL, replay.head_sha, language="python",
                    build_mode="none", query_suite=SUITE,
                    timeout_seconds=120,
                )
            self.assertEqual(findings, [])
            self.assertEqual(metadata["status"], "ok")
            self.assertEqual(
                replay.calls,
                ["git", "git", "git", "codeql", "codeql"],
            )

    def test_original_worker_records_security_finding_with_cwe(self):
        with LocalCodeQLReplay() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/codeql-snapshots",
                "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 8, "html_url": REPO_URL + "/pull/8",
                "base": {"ref": "main", "sha": replay.base_sha},
                "head": {"ref": "fixture", "sha": replay.head_sha},
            })
            issue = db.upsert_issue(repo, {
                "number": 7, "html_url": REPO_URL + "/issues/7",
                "title": "Fabricated introduced CodeQL marker",
                "body": "Only synthetic code and fake CLI", "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "fabricated")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class StrictCodeQLBackend(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.real_original_scans = 0

                def scan_snapshot_with_codeql(
                    self, repo_url, sha, *, language,
                    build_mode, query_suite, timeout_seconds,
                ):
                    self.real_original_scans += 1
                    return replay.scan(
                        repo_url, sha, language=language,
                        build_mode=build_mode, query_suite=query_suite,
                        timeout_seconds=timeout_seconds,
                    )

            queue = load_original_queue(db)
            self.assertEqual(queue["seed_scanner_jobs"](db), 6)
            job = queue["claim_job"](
                db, ["codeql"], worker_id="synthetic-codeql-worker",
            )
            backend = StrictCodeQLBackend()
            ArchivedFixtureWorker(db, backend).run(job, settings())
            self.assertEqual(backend.real_original_scans, 2)
            self.assertEqual(
                db.one(
                    "SELECT status FROM scanner_jobs WHERE id=?", (job.id,),
                )["status"],
                "ok",
            )
            runs = db.query(
                "SELECT scanner,status FROM scanner_runs WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual(
                [(item["scanner"], item["status"]) for item in runs],
                [
                    ("codeql-python-base", "ok"),
                    ("codeql-python-head", "ok"),
                    ("codeql-base", "ok"),
                    ("codeql-head", "ok"),
                    ("codeql", "ok"),
                ],
            )
            finding = db.one(
                "SELECT scanner,finding_type,rule_id,cwe,file_path,line,introduced "
                "FROM scanner_findings WHERE case_id=?", (case_id,),
            )
            self.assertEqual(
                (
                    finding["scanner"], finding["finding_type"],
                    finding["rule_id"], finding["file_path"],
                    finding["line"], finding["introduced"],
                ),
                ("codeql", "vulnerability", RULE, FILENAME, 5, 1),
            )
            self.assertIn("cwe-078", finding["cwe"])
            self.assertEqual(
                db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
