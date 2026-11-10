"""Exact historical scan_case orchestration with synthetic scanner providers."""
from __future__ import annotations

import json
import socket
import subprocess
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_fixture_scan_case import (
    ArchivedFixtureScanCase, FixtureScannerProviders, MissingScannerFixture,
)


class SyntheticArchivedScanCaseTests(unittest.TestCase):
    def setUp(self):
        ctx = disposable_original_database()
        self.db = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        self.repo_id = self.db.insert_or_get_repo({
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
        })
        self.pr_id = self.db.upsert_pr(self.repo_id, {
            "number": 12,
            "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8", "body": "Fixes #8",
            "head": {"ref": "codex/fix", "sha": "headfixture"},
            "base": {"ref": "main", "sha": "basefixture"},
        })
        issue_id = self.db.upsert_issue(self.repo_id, {
            "number": 8, "html_url": "https://example.invalid/example/repo/issues/8",
            "title": "Build regression",
            "body": "Please fix the failing TypeScript build in src/app.ts.",
            "labels": [],
        }, 8, True)
        self.db.link_issue_pr(issue_id, self.pr_id, "closing-keyword")
        self.case_id = self.db.create_or_get_case(
            self.repo_id, issue_id, self.pr_id, "AI-explicit-high", ["AI-explicit-high"],
        )
        self.db.replace_pr_files(self.pr_id, [{
            "filename": "src/app.ts", "patch": "@@ -1 +1 @@\n-old\n+new\n",
            "status": "modified", "additions": 1,
        }])
        self.case = {
            "case_id": self.case_id, "pr_id": self.pr_id,
            "repo_url": "https://example.invalid/example/repo",
            "base_sha": "basefixture", "head_sha": "headfixture",
        }
        self.config = {
            "scanners": {
                "gitleaks": False, "dependency_downgrade": False,
                "osv": False, "trivy": False, "semgrep": False,
                "codeql": False,
            },
            "cache": {"force_rescan": False},
        }

    def run_rows(self):
        return self.db.query("SELECT scanner,status,stdout,stderr FROM scanner_runs WHERE case_id=? ORDER BY id", (self.case_id,))

    def finding_rows(self):
        return self.db.query("SELECT scanner,finding_type,description,raw_json FROM scanner_findings WHERE case_id=? ORDER BY id", (self.case_id,))

    def scanner(self, backends):
        return ArchivedFixtureScanCase(self.db, backends)

    def test_gitleaks_actual_archived_branch_records_synthetic_evidence(self):
        self.config["scanners"]["gitleaks"] = True
        backends = FixtureScannerProviders(gitleaks=[
            ([{"description": "synthetic leaked credential", "severity": "HIGH",
               "introduced": True, "rule": "fixture-credential"}],
             {"status": "ok", "stdout": "fixture-ok", "stderr": ""}),
        ])
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("external scanner")):
                self.scanner(backends).run(self.case, self.config)
        self.assertEqual([r["scanner"] for r in self.run_rows()], ["gitleaks"])
        self.assertEqual(self.run_rows()[0]["stdout"], "fixture-ok")
        self.assertEqual(self.finding_rows()[0]["finding_type"], "secret")
        self.assertEqual(backends.calls, [("gitleaks", 1)])
        queue = load_original_queue(self.db)
        queue["update_case_stages"](self.db)
        self.assertEqual(self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"], "needs_review")

    def test_original_cache_skips_repeated_gitleaks_backend_call(self):
        self.config["scanners"]["gitleaks"] = True
        backends = FixtureScannerProviders(gitleaks=[
            ([], {"status": "ok", "stdout": "fixture", "stderr": ""}),
        ])
        scanner = self.scanner(backends)
        scanner.run(self.case, self.config)
        scanner.run(self.case, self.config)
        self.assertEqual(len(backends.calls), 1)
        self.assertEqual(len(self.run_rows()), 1)

    def test_original_force_rescan_replaces_prior_gitleaks_evidence(self):
        self.config["scanners"]["gitleaks"] = True
        backends = FixtureScannerProviders(gitleaks=[
            ([{"description":"old synthetic"}], {"status":"ok"}),
            ([{"description":"new synthetic"}], {"status":"ok"}),
        ])
        scanner = self.scanner(backends)
        scanner.run(self.case, self.config)
        self.config["cache"]["force_rescan"] = True
        scanner.run(self.case, self.config)
        self.assertEqual(len(self.run_rows()), 1)
        self.assertEqual([r["description"] for r in self.finding_rows()], ["new synthetic"])
        self.assertEqual(len(backends.calls), 2)

    def test_codeql_actual_branch_uses_two_snapshot_fixtures_and_diff(self):
        self.config["scanners"]["codeql"] = True
        find = {"rule": "SYNTHETIC-CWE", "description": "new sink",
                "file": "src/app.ts", "line": 1, "cwe": "CWE-79"}
        backends = FixtureScannerProviders(codeql={
            "basefixture": ([], {"status":"ok"}),
            "headfixture": ([find], {"status":"ok"}),
        })
        self.scanner(backends).run(self.case, self.config)
        self.assertEqual(
            [r["scanner"] for r in self.run_rows()],
            ["codeql-javascript-typescript-base", "codeql-javascript-typescript-head",
             "codeql-base", "codeql-head", "codeql"],
        )
        finding = self.finding_rows()[0]
        self.assertEqual((finding["scanner"], finding["finding_type"]), ("codeql", "vulnerability"))
        self.assertEqual(json.loads(finding["raw_json"])["diff_linked"], True)
        self.assertEqual(len(backends.calls), 2)
        self.assertIn("introduced_total=1", self.run_rows()[-1]["stdout"])
        self.assertIn("security_diff_linked=1", self.run_rows()[-1]["stdout"])

    def test_codeql_no_patch_cannot_diff_link_synthetic_finding(self):
        self.config["scanners"]["codeql"] = True
        self.db.replace_pr_files(self.pr_id, [{
            "filename": "src/app.ts", "patch": None,
            "status": "modified", "additions": 1,
        }])
        find = {"rule":"SYNTHETIC","description":"synthetic",
                "file":"src/app.ts","line":1,"cwe":"CWE-79"}
        backends = FixtureScannerProviders(codeql={
            "basefixture": ([], {"status":"ok"}),
            "headfixture": ([find], {"status":"ok"}),
        })
        self.scanner(backends).run(self.case, self.config)
        self.assertEqual(self.finding_rows(), [])
        self.assertIn("introduced_total=1", self.run_rows()[-1]["stdout"])
        self.assertIn("diff_linked=0", self.run_rows()[-1]["stdout"])

    def test_codeql_failed_base_records_error_without_findings(self):
        self.config["scanners"]["codeql"] = True
        backends = FixtureScannerProviders(codeql={
            "basefixture": ([], {"status":"error","stderr":"synthetic error"}),
            "headfixture": ([{"rule":"x","file":"src/app.ts","line":1}], {"status":"ok"}),
        })
        self.scanner(backends).run(self.case, self.config)
        self.assertEqual(self.finding_rows(), [])
        self.assertEqual(self.run_rows()[-1]["status"], "error")

    def test_codeql_trigger_disabled_records_not_applicable_without_provider(self):
        self.config["scanners"]["codeql"] = True
        self.config["scanners"]["codeql_trigger"] = "none"
        backends = FixtureScannerProviders()
        self.scanner(backends).run(self.case, self.config)
        self.assertEqual([r["scanner"] for r in self.run_rows()], ["codeql-base", "codeql-head", "codeql"])
        self.assertEqual({r["status"] for r in self.run_rows()}, {"not_applicable"})
        self.assertEqual(backends.calls, [])

    def test_incomplete_snapshot_fails_closed_even_if_base_was_recorded(self):
        self.config["scanners"]["codeql"] = True
        backends = FixtureScannerProviders(codeql={
            "basefixture": ([], {"status":"ok"}),
        })
        with self.assertRaises(MissingScannerFixture):
            self.scanner(backends).run(self.case, self.config)
        # The historical function writes base status before reading head data.
        self.assertEqual([r["scanner"] for r in self.run_rows()], ["codeql-javascript-typescript-base"])

    def test_missing_semgrep_fixture_fails_closed_with_no_scanner_rows(self):
        self.config["scanners"]["semgrep"] = True
        backends = FixtureScannerProviders()
        with self.assertRaises(MissingScannerFixture):
            self.scanner(backends).run(self.case, self.config)
        self.assertEqual(self.run_rows(), [])
        self.assertEqual(backends.calls, [])

    def test_non_synthetic_repo_url_is_rejected(self):
        self.config["scanners"]["codeql"] = True
        self.case["repo_url"] = "https://github.com/real/private-repo"
        with self.assertRaises(ValueError):
            self.scanner(FixtureScannerProviders()).run(self.case, self.config)
        self.assertEqual(self.run_rows(), [])

    def test_malformed_case_identity_rejected(self):
        self.config["scanners"]["gitleaks"] = True
        self.case["case_id"] = 999999
        with self.assertRaises(ValueError):
            self.scanner(FixtureScannerProviders()).run(self.case, self.config)
        self.assertEqual(self.run_rows(), [])

    def test_requires_all_six_explicit_flags(self):
        self.config["scanners"].pop("osv")
        with self.assertRaises(ValueError):
            self.scanner(FixtureScannerProviders()).run(self.case, self.config)
