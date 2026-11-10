"""Four more exact original scan_case branches, using synthetic-only outputs.

No scanner binaries, real repositories, original databases, or network calls.
"""
from __future__ import annotations

import json
import socket
import subprocess
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import (
    ArchivedFixtureScanCase, FixtureScannerProviders, MissingScannerFixture,
)
from tests.support.archived_job_queue_contract import load_original_queue


class OtherArchivedScannerBranchesTests(unittest.TestCase):
    def setUp(self):
        ctx = disposable_original_database()
        self.db = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        repo = self.db.insert_or_get_repo({
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
        })
        pr = self.db.upsert_pr(repo, {
            "number": 42, "html_url": "https://example.invalid/example/repo/pull/42",
            "head": {"ref": "fixture", "sha": "synthetic-head"},
            "base": {"ref": "main", "sha": "synthetic-base"},
        })
        issue = self.db.upsert_issue(repo, {
            "number": 9, "html_url": "https://example.invalid/example/repo/issues/9",
            "title": "Synthetic build issue", "body": "Synthetic only", "labels": [],
        }, 2, True)
        self.db.link_issue_pr(issue, pr, "fixture")
        self.case_id = self.db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
        self.pr_id = pr
        self.case = {
            "case_id": self.case_id, "pr_id": pr,
            "repo_url": "https://example.invalid/example/repo",
            "base_sha": "synthetic-base", "head_sha": "synthetic-head",
        }
        self.cfg = {
            "scanners": {
                "gitleaks": False, "dependency_downgrade": False,
                "osv": False, "trivy": False, "semgrep": False,
                "codeql": False,
            },
            "cache": {"force_rescan": False},
        }
        self.db.replace_pr_files(pr, [{
            "filename": "requirements.txt", "category": "dependency",
            "status": "modified", "additions": 1, "deletions": 1,
            "patch": "@@ -1 +1 @@\n-lib==2.0\n+lib==1.0\n",
        }])

    def runs(self, scanner=None):
        if scanner:
            return self.db.query(
                "SELECT scanner,status,stdout,stderr FROM scanner_runs WHERE case_id=? AND scanner=? ORDER BY id",
                (self.case_id, scanner),
            )
        return self.db.query(
            "SELECT scanner,status,stdout,stderr FROM scanner_runs WHERE case_id=? ORDER BY id",
            (self.case_id,),
        )

    def findings(self):
        return self.db.query(
            "SELECT scanner,finding_type,rule_id,description,evidence,raw_json FROM scanner_findings WHERE case_id=? ORDER BY id",
            (self.case_id,),
        )

    def scan(self, backends):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("external scanner")):
                ArchivedFixtureScanCase(self.db, backends).run(self.case, self.cfg)

    def test_dependency_diff_records_regression_and_is_cached(self):
        self.cfg["scanners"]["dependency_downgrade"] = True
        b = FixtureScannerProviders(dependency_diff=[[{
            "package": "lib", "old_version": "2.0", "new_version": "1.0",
            "change_type": "dependency_downgrade",
            "description": "SYNTHETIC downgrade", "file": "requirements.txt",
            "introduced": True,
        }]])
        self.scan(b)
        self.scan(b)
        self.assertEqual([(r["scanner"], r["status"]) for r in self.runs()], [("dependency-diff", "ok")])
        self.assertEqual((self.findings()[0]["scanner"], self.findings()[0]["finding_type"]), ("dependency-diff", "dependency"))
        self.assertEqual(b.calls, [("dependency-diff", 1)])

    def test_dependency_diff_clean_without_category_is_not_applicable(self):
        self.cfg["scanners"]["dependency_downgrade"] = True
        self.db.replace_pr_files(self.pr_id, [{
            "filename": "src/app.ts", "status": "modified", "patch": "@@ -1 +1 @@\n-old\n+new\n",
        }])
        self.scan(FixtureScannerProviders(dependency_diff=[[]]))
        self.assertEqual(self.runs("dependency-diff")[0]["status"], "not_applicable")
        self.assertEqual(self.findings(), [])

    def test_osv_preserves_original_base_head_and_summary_evidence(self):
        self.cfg["scanners"]["osv"] = True
        long_stdout = "b" * 5200
        f = {"package": "fixture-lib", "vuln_id": "SYNTHETIC-OSV-1", "severity": "HIGH",
             "description": "Synthetic dependency alert", "raw": {"id": "SYNTHETIC-OSV-1"}}
        b = FixtureScannerProviders(osv=[(
            [f],
            {"status": "ok", "stdout": long_stdout},
            {"status": "ok", "stdout": long_stdout},
            {"status": "ok_with_warnings", "stderr": "synthetic warning"},
        )])
        self.scan(b)
        self.assertEqual([(x["scanner"], x["status"]) for x in self.runs()],
                         [("osv-base", "ok"), ("osv-head", "ok_with_warnings"), ("osv-scanner", "ok")])
        self.assertEqual(len(self.runs("osv-base")[0]["stdout"]), 5200)
        self.assertEqual(len(self.runs("osv-scanner")[0]["stdout"]), 5000)
        finding = self.findings()[0]
        self.assertEqual((finding["scanner"], finding["finding_type"], finding["rule_id"]),
                         ("osv-scanner", "dependency", "SYNTHETIC-OSV-1"))
        self.assertEqual(json.loads(finding["raw_json"]), {"id": "SYNTHETIC-OSV-1"})
        self.assertEqual(b.calls, [("osv", "synthetic-base", "synthetic-head", 300, 1)])

    def test_trivy_records_failed_scan_and_still_persists_returned_findings(self):
        self.cfg["scanners"]["trivy"] = True
        b = FixtureScannerProviders(trivy=[(
            [{"package": "fixture-lib", "vuln_id": "SYNTHETIC-CVE-1",
              "description": "Synthetic only", "introduced": True}],
            {"status": "error", "stderr": "synthetic failure"},
            {"status": "ok"}, {"status": "error", "stderr": "head failed"},
        )])
        self.scan(b)
        self.assertEqual([(x["scanner"], x["status"]) for x in self.runs()],
                         [("trivy-base", "ok"), ("trivy-head", "error"), ("trivy-scanner", "error")])
        self.assertEqual(self.findings()[0]["scanner"], "trivy-scanner")
        self.assertEqual(b.calls, [("trivy", "synthetic-base", "synthetic-head", 600, 1)])

    def test_semgrep_default_finding_type_and_configuration_passthrough(self):
        self.cfg["scanners"].update({
            "semgrep": True, "semgrep_config": "synthetic-rules",
            "semgrep_timeout_seconds": 17,
        })
        b = FixtureScannerProviders(semgrep=[(
            [{"rule": "SYNTHETIC-S1", "description": "Synthetic suspect pattern"}],
            {"status": "ok", "stdout": "synthetic-only"},
        )])
        self.scan(b)
        self.assertEqual(self.runs("semgrep")[0]["stdout"], "synthetic-only")
        self.assertEqual((self.findings()[0]["scanner"], self.findings()[0]["finding_type"]),
                         ("semgrep", "vulnerability"))
        self.assertEqual(b.calls, [("semgrep", "synthetic-head", "synthetic-rules", 17, 1)])

    def test_semgrep_missing_head_is_explicitly_not_applicable(self):
        self.cfg["scanners"]["semgrep"] = True
        self.case.pop("head_sha")
        b = FixtureScannerProviders()
        self.scan(b)
        self.assertEqual(self.runs("semgrep")[0]["status"], "not_applicable")
        self.assertEqual(self.findings(), [])
        self.assertEqual(b.calls, [])

    def test_missing_osv_fixture_fails_closed_not_clean(self):
        self.cfg["scanners"]["osv"] = True
        with self.assertRaises(MissingScannerFixture):
            self.scan(FixtureScannerProviders())
        self.assertEqual(self.runs(), [])

    def test_missing_dependency_diff_fixture_fails_closed_not_clean(self):
        self.cfg["scanners"]["dependency_downgrade"] = True
        with self.assertRaises(MissingScannerFixture):
            self.scan(FixtureScannerProviders())
        self.assertEqual(self.runs(), [])

    def test_malformed_trivy_fixture_fails_closed_not_clean(self):
        self.cfg["scanners"]["trivy"] = True
        with self.assertRaises(MissingScannerFixture):
            self.scan(FixtureScannerProviders(trivy=[([], {"status": "ok"})]))
        self.assertEqual(self.runs(), [])

    def test_osv_force_rescan_preserves_trivy_findings(self):
        self.cfg["scanners"]["osv"] = True
        b = FixtureScannerProviders(osv=[([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"})])
        self.scan(b)
        self.db.execute(
            "INSERT INTO scanner_findings(case_id,pr_id,scanner,finding_type,description) VALUES(?,?,?,?,?)",
            (self.case_id, self.pr_id, "trivy-scanner", "dependency", "unrelated synthetic Trivy finding"),
        )
        self.cfg["cache"]["force_rescan"] = True
        b.osv_responses.append(([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"}))
        self.scan(b)
        self.assertEqual([x["scanner"] for x in self.findings()], ["trivy-scanner"])
        self.assertEqual(len(self.runs("osv-scanner")), 1)

    def test_dependency_diff_force_rescan_erases_other_scanner_dependency_finding(self):
        """Historical scanner cleanup bug, observed but NOT silently fixed."""
        self.cfg["scanners"]["dependency_downgrade"] = True
        b = FixtureScannerProviders(dependency_diff=[[], []])
        self.scan(b)
        self.db.execute(
            "INSERT INTO scanner_findings(case_id,pr_id,scanner,finding_type,description) VALUES(?,?,?,?,?)",
            (self.case_id, self.pr_id, "osv-scanner", "dependency", "independent synthetic OSV"),
        )
        self.cfg["cache"]["force_rescan"] = True
        self.scan(b)
        self.assertEqual(self.findings(), [])
        self.assertEqual(len(self.runs("dependency-diff")), 1)

    def test_six_scanner_branches_bridge_into_original_queue(self):
        self.cfg["scanners"].update({
            "gitleaks": True, "dependency_downgrade": True,
            "osv": True, "trivy": True, "semgrep": True, "codeql": True,
            "codeql_trigger": "none",
        })
        backends = FixtureScannerProviders(
            gitleaks=[([], {"status": "ok"})],
            dependency_diff=[[]],
            osv=[([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"})],
            trivy=[([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"})],
            semgrep=[([], {"status": "ok"})],
        )
        self.scan(backends)
        self.assertEqual(
            [x["scanner"] for x in self.runs()],
            ["gitleaks", "dependency-diff", "osv-base", "osv-head", "osv-scanner",
             "trivy-base", "trivy-head", "trivy-scanner", "semgrep",
             "codeql-base", "codeql-head", "codeql"],
        )
        queue = load_original_queue(self.db)
        self.assertEqual(queue["seed_scanner_jobs"](self.db), 6)
        queue["sync_jobs_from_scanner_runs"](self.db, self.case_id)
        jobs = self.db.query(
            "SELECT job_type,status FROM scanner_jobs WHERE case_id=? ORDER BY job_type", (self.case_id,),
        )
        self.assertEqual(len(jobs), 6)
        self.assertEqual({x["status"] for x in jobs}, {"ok", "not_applicable"})
        queue["update_case_stages"](self.db)
        self.assertEqual(self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"],
                         "scan_blocked")
        self.assertEqual(self.findings(), [])


if __name__ == "__main__":
    unittest.main()
