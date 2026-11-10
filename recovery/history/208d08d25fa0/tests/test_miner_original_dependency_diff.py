"""Byte-for-byte original pure dependency-diff, worker and SQLite integration.

Everything is synthetic. Never imports historical worker/scanner runner modules,
executes scanner binaries, creates remote requests or opens Wits databases.
"""
from __future__ import annotations

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import socket
import subprocess
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from src.scanners import dependency_diff as original
from tests.support.archived_fixture_scan_case import (
    ArchivedFixtureScanCase, MissingScannerFixture,
)
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.original_dependency_diff_provider import (
    OriginalDependencyDiffProvider,
)

EXPECTED_SHA256 = "14fef8ed753361b09fbe39f09849d45cdb73264aad93f542d6d8e2d7e95e43d7"
FIXTURE_FILENAME = "fixture/requirements.txt"


def modified_file(patch, *, filename=FIXTURE_FILENAME):
    return {"filename": filename, "status": "modified", "category": "dependency",
            "patch": patch, "additions": 1, "deletions": 1}


def selected_config(*, force=False):
    return {
        "scanners": {
            "gitleaks": False, "dependency_downgrade": True,
            "osv": False, "trivy": False, "semgrep": False, "codeql": False,
        },
        "cache": {"force_rescan": force},
    }


class OriginalDependencyDiffPureTests(unittest.TestCase):
    def test_original_bytes_sha_match_across_active_and_three_archives(self):
        root = Path(__file__).resolve().parents[1]
        sources = [
            root / "src/scanners/dependency_diff.py",
            *(root / "historical/miner" / stamp / "src/scanners/dependency_diff.py"
              for stamp in ("2026-08-17", "2026-08-19", "2026-10-20-live-export")),
        ]
        blobs = [source.read_bytes() for source in sources]
        for source, blob in zip(sources, blobs):
            with self.subTest(source=str(source.relative_to(root))):
                self.assertEqual(blob, blobs[0])
                self.assertEqual(hashlib.sha256(blob).hexdigest(), EXPECTED_SHA256)

    def test_version_parser_is_explicitly_pinned_candidate(self):
        self.assertEqual(version("packaging"), "25.0")

    def test_original_requirements_downgrade_preserves_new_side_line_number(self):
        patch = "@@ -9,2 +12,2 @@\n-synthetic_pkg==3.0\n+synthetic_pkg==2.1\n unchanged\n"
        findings = original.detect_dependency_regressions([modified_file(patch)])
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(
            (findings[0]["package"], findings[0]["old_version"],
             findings[0]["new_version"], findings[0]["line"],
             findings[0]["change_type"]),
            ("synthetic_pkg", "3.0", "2.1", 12, "dependency_downgrade"),
        )
        self.assertEqual(findings[0]["file"], FIXTURE_FILENAME)

    def test_equal_version_exact_to_lower_bound_is_original_constraint_widening(self):
        patch = "@@ -1 +1 @@\n-synthetic_pkg==2.5\n+synthetic_pkg>=2.5\n"
        findings = original.detect_dependency_regressions([modified_file(patch)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["change_type"], "constraint_widened")
        self.assertEqual(findings[0]["old_version"], "2.5")
        self.assertEqual(findings[0]["new_version"], "2.5")

    def test_nonpep440_versions_with_operator_change_are_flagged_as_constraint_changed(self):
        patch = "@@ -1 +1 @@\n-synthetic_pkg==custom-main\n+synthetic_pkg>=custom-next\n"
        findings = original.detect_dependency_regressions([modified_file(patch)])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["change_type"], "constraint_changed")
        self.assertEqual((findings[0]["old_version"], findings[0]["new_version"]),
                         ("custom-main", "custom-next"))

    def test_new_dependencies_and_upgrades_are_changes_but_not_regressions(self):
        patch = ("@@ -1,1 +1,2 @@\n-synthetic_pkg==1.0\n"
                 "+synthetic_pkg==2.0\n+new_fixture==1.0\n")
        changes = original.detect_dependency_changes([modified_file(patch)])
        self.assertEqual([x["change_type"] for x in changes], ["added_dependency"])
        self.assertEqual(changes[0]["package"], "new_fixture")
        self.assertEqual(changes[0]["line"], 2)
        self.assertEqual(original.detect_dependency_regressions([modified_file(patch)]), [])

    def test_original_package_json_heuristic_downgrades_version_shaped_field(self):
        patch = ('@@ -1 +1 @@\n-  "fixture-package": "^2.4",\n'
                 '+  "fixture-package": "1.8",\n')
        findings = original.detect_dependency_regressions([
            modified_file(patch, filename="fixture/package.json")
        ])
        self.assertEqual(len(findings), 1)
        self.assertEqual((findings[0]["package"], findings[0]["change_type"],
                          findings[0]["line"]),
                         ("fixture-package", "dependency_downgrade", 1))

    def test_original_json_parser_can_misclassify_non_dependency_metadata(self):
        patch = '@@ -1 +1 @@\n-  "build": "2026",\n+  "build": "2025",\n'
        findings = original.detect_dependency_regressions([
            modified_file(patch, filename="fixture/package.json")
        ])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["package"], "build")
        self.assertEqual(findings[0]["change_type"], "dependency_downgrade")

    def test_original_dependency_path_suffix_is_permissive(self):
        self.assertTrue(original.is_dependency_file("fixture/notreallyrequirements.txt"))
        self.assertTrue(original.is_dependency_file("fixture/package-lock.json"))
        self.assertFalse(original.is_dependency_file("fixture/app.py"))

    def test_missing_patch_does_not_imply_no_dependency_change(self):
        self.assertEqual(original.detect_dependency_changes([modified_file(None)]), [])
        self.assertEqual(original.detect_dependency_regressions([modified_file(None)]), [])

    def test_badly_formatted_hunk_omits_line_but_can_still_record_change(self):
        patch = "-synthetic_pkg==5.0\n+synthetic_pkg==4.0\n"
        findings = original.detect_dependency_regressions([modified_file(patch)])
        self.assertEqual(len(findings), 1)
        self.assertIsNone(findings[0]["line"])


class OriginalDependencyDiffArchivedWorkerTests(unittest.TestCase):
    def setUp(self):
        ctx = disposable_original_database()
        self.db = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        repo = self.db.insert_or_get_repo({
            "full_name": "fixture/dependency-replay",
            "html_url": "https://example.invalid/fixture/dependency-replay",
        })
        self.pr_id = self.db.upsert_pr(repo, {
            "number": 33,
            "html_url": "https://example.invalid/fixture/dependency-replay/pull/33",
            "head": {"ref": "fixture", "sha": "fixture-head"},
            "base": {"ref": "main", "sha": "fixture-base"},
        })
        issue = self.db.upsert_issue(repo, {
            "number": 10,
            "html_url": "https://example.invalid/fixture/dependency-replay/issues/10",
            "title": "Fabricated build regression",
            "body": "Please adjust fixture versions only",
            "labels": [],
        }, 5, True)
        self.db.link_issue_pr(issue, self.pr_id, "synthetic")
        self.case_id = self.db.create_or_get_case(repo, issue, self.pr_id, "AI-unknown", [])
        self.case = {
            "case_id": self.case_id, "pr_id": self.pr_id,
            "repo_url": "https://example.invalid/fixture/dependency-replay",
            "base_sha": "fixture-base", "head_sha": "fixture-head",
        }
        self.patch = "@@ -1 +1 @@\n-synthetic_lib==6.0\n+synthetic_lib==5.0\n"
        self.db.replace_pr_files(self.pr_id, [modified_file(self.patch)])
        self.queue = load_original_queue(self.db)

    def run_worker(self, provider):
        self.queue["seed_scanner_jobs"](self.db)
        job = self.queue["claim_job"](
            self.db, ["dependency_downgrade"], worker_id="exact-parser-fixture",
        )
        self.assertIsNotNone(job)
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess")):
                ArchivedFixtureWorker(self.db, provider).run(
                    job, FixtureWorkerSettings(selected_config()),
                )
        return job

    def test_actual_original_parser_flows_through_worker_into_sqlite(self):
        provider = OriginalDependencyDiffProvider(expected_patch=self.patch)
        job = self.run_worker(provider)
        self.assertEqual(provider.calls, [("dependency-diff-original", 1)])
        self.assertEqual(self.db.one(
            "SELECT status,attempts FROM scanner_jobs WHERE id=?", (job.id,)
        )["status"], "ok")
        self.assertEqual(self.db.one(
            "SELECT scanner,status FROM scanner_runs WHERE case_id=?", (self.case_id,)
        )["scanner"], "dependency-diff")
        f = self.db.one(
            "SELECT scanner,finding_type,description,introduced,line,evidence,raw_json "
            "FROM scanner_findings WHERE case_id=?", (self.case_id,),
        )
        self.assertEqual((f["scanner"], f["finding_type"], f["introduced"], f["line"]),
                         ("dependency-diff", "dependency", 1, 1))
        payload = json.loads(f["raw_json"])
        self.assertEqual(payload["change_type"], "dependency_downgrade")
        self.assertEqual((payload["old_version"], payload["new_version"]), ("6.0", "5.0"))
        self.assertEqual(self.db.one(
            "SELECT status FROM cases WHERE id=?", (self.case_id,)
        )["status"], "needs_review")

    def test_cache_preserves_previous_original_regression_result(self):
        provider = OriginalDependencyDiffProvider(expected_patch=self.patch)
        scanner = ArchivedFixtureScanCase(self.db, provider)
        scanner.run(self.case, selected_config())
        scanner.run(self.case, selected_config())
        self.assertEqual(provider.calls, [("dependency-diff-original", 1)])
        self.assertEqual(self.db.one(
            "SELECT COUNT(*) AS n FROM scanner_runs WHERE case_id=?", (self.case_id,)
        )["n"], 1)

    def test_forced_original_rescan_deletes_other_scanner_dependency_findings(self):
        provider = OriginalDependencyDiffProvider(expected_patch=self.patch)
        scanner = ArchivedFixtureScanCase(self.db, provider)
        scanner.run(self.case, selected_config())
        self.db.execute(
            "INSERT INTO scanner_findings(case_id,pr_id,scanner,finding_type,description) "
            "VALUES(?,?,'osv-scanner','dependency','synthetic OSV finding')",
            (self.case_id, self.pr_id),
        )
        scanner.run(self.case, selected_config(force=True))
        actual = self.db.query(
            "SELECT scanner,description FROM scanner_findings WHERE case_id=? ORDER BY id",
            (self.case_id,),
        )
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["scanner"], "dependency-diff")
        self.assertEqual(provider.calls, [
            ("dependency-diff-original", 1), ("dependency-diff-original", 1)
        ])

    def test_wrong_patch_aborts_without_being_mistaken_for_clean(self):
        provider = OriginalDependencyDiffProvider(expected_patch="@synthetic-only wrong")
        with self.assertRaises(MissingScannerFixture):
            self.run_worker(provider)
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.db.one(
            "SELECT status FROM scanner_jobs WHERE case_id=? AND job_type='dependency_downgrade'",
            (self.case_id,),
        )["status"], "running")
        self.assertEqual(self.db.query(
            "SELECT * FROM scanner_findings WHERE case_id=?", (self.case_id,),
        ), [])

    def test_missing_patch_is_recorded_as_original_no_findings_not_proof_of_clean(self):
        self.db.replace_pr_files(self.pr_id, [modified_file(None)])
        provider = OriginalDependencyDiffProvider(expected_patch=None)
        job = self.run_worker(provider)
        self.assertEqual(provider.calls, [("dependency-diff-original", 1)])
        self.assertEqual(self.db.query(
            "SELECT * FROM scanner_findings WHERE case_id=?", (self.case_id,),
        ), [])
        self.assertEqual(self.db.one(
            "SELECT status FROM scanner_jobs WHERE id=?", (job.id,)
        )["status"], "ok")
        self.assertEqual(self.db.one(
            "SELECT status FROM cases WHERE id=?", (self.case_id,)
        )["status"], "scanner_running")


if __name__ == "__main__":
    unittest.main()
