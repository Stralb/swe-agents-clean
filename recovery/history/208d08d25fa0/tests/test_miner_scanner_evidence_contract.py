"""Exact historical scanner evidence and synthetic scanner-job integration.

No scanner binaries, network, clones, Slurm or Wits database calls occur.
"""
from __future__ import annotations

import hashlib
import json
import socket
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support import archived_job_queue_contract as queue_contract
from tests.support import archived_scanner_records_contract as scanner_contract


class OriginalScannerEvidenceTests(unittest.TestCase):
    def setUp(self):
        context = disposable_original_database()
        self.db = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.records = scanner_contract.load_archived_scanner_records(self.db)
        self.queue = queue_contract.load_original_queue(self.db)
        self.repo_id = self.db.insert_or_get_repo({
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
        })
        self.pr_id = self.db.upsert_pr(self.repo_id, {
            "number": 12, "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8", "body": "Fixes #8",
            "head": {"ref": "codex/fix", "sha": "123"},
            "base": {"ref": "main", "sha": "456"},
        })
        self.issue_id = self.db.upsert_issue(self.repo_id, {
            "number": 8, "html_url": "https://example.invalid/example/repo/issues/8",
            "title": "Build regression",
            "body": "Please fix src/app.ts; behavior must be preserved.",
            "labels": [],
        }, 8, True)
        self.db.link_issue_pr(self.issue_id, self.pr_id, "closing-keyword")
        self.case_id = self.db.create_or_get_case(
            self.repo_id, self.issue_id, self.pr_id,
            "AI-explicit-high", ["AI-explicit-high"],
        )
        self.db.replace_pr_files(self.pr_id, [{
            "filename": "src/app.ts", "status": "modified", "additions": 1,
            "patch": "@@ -1 +1 @@\n-old\n+new",
        }])

    def run_row(self, scanner):
        return self.db.one(
            "SELECT * FROM scanner_runs WHERE case_id=? AND scanner=? ORDER BY id DESC LIMIT 1",
            (self.case_id, scanner),
        )

    def findings(self):
        return self.db.query(
            "SELECT * FROM scanner_findings WHERE case_id=? ORDER BY id",
            (self.case_id,),
        )

    def record_run(self, scanner, status="ok", **kwargs):
        self.records["_insert_run"](
            self.db, self.case_id, self.pr_id, scanner, status, **kwargs,
        )

    def record_finding(self, scanner, finding_type, finding):
        self.records["_insert_finding"](
            self.db, self.case_id, self.pr_id, scanner, finding_type, finding,
        )

    def case_status(self):
        return self.db.one(
            "SELECT status, downstream_signal, auto_tags FROM cases WHERE id=?",
            (self.case_id,),
        )

    def test_source_hash_matches_three_original_archives(self):
        raw = scanner_contract.SOURCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), scanner_contract.SOURCE_SHA256)
        root = Path(__file__).resolve().parents[1]
        for stamp in ("2026-08-17", "2026-08-19", "2026-10-20-live-export"):
            with self.subTest(stamp=stamp):
                self.assertEqual(
                    (root/"historical/miner"/stamp/"src/scanners/scanner_runner.py").read_bytes(),
                    raw,
                )

    def test_only_recording_functions_can_be_executed(self):
        self.assertEqual(set(self.records), set(scanner_contract.ALLOWLIST))
        self.assertNotIn("scan_case", self.records)
        self.assertNotIn("scan_snapshot_with_codeql", self.records)
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("tool run")):
                self.record_run("semgrep")
        self.assertEqual(self.run_row("semgrep")["status"], "ok")

    def test_run_stdout_is_tail_truncated_by_default(self):
        self.record_run("gitleaks", stdout="A"*7000, stderr="B"*6001)
        row = self.run_row("gitleaks")
        self.assertEqual(row["stdout"], "A"*5000)
        self.assertEqual(row["stderr"], "B"*5000)

    def test_run_full_output_preserved_for_snapshot_evidence(self):
        self.record_run("osv-base", stdout="X"*7001, preserve_full=True)
        self.assertEqual(len(self.run_row("osv-base")["stdout"]), 7001)

    def test_finding_serialization_and_rule_fallback(self):
        self.record_finding("trivy-scanner", "dependency", {
            "package": "example-lib", "version": "1.2", "vuln_id": "CVE-SYNTHETIC",
            "severity": "HIGH", "introduced": True,
        })
        row = self.findings()[0]
        self.assertEqual(row["rule_id"], "CVE-SYNTHETIC")
        self.assertEqual(row["introduced"], 1)
        self.assertEqual(json.loads(row["evidence"]),
                         {"package":"example-lib","version":"1.2","vuln_id":"CVE-SYNTHETIC"})
        self.assertEqual(json.loads(row["raw_json"])["severity"], "HIGH")

    def test_string_evidence_and_raw_are_not_double_encoded(self):
        self.record_finding("gitleaks", "secret", {
            "introduced": False, "evidence": "masked-token", "raw": '{"demo":true}',
            "rule": "synthetic-secret-rule", "file": "src/app.ts", "line": 8,
        })
        row = self.findings()[0]
        self.assertEqual((row["evidence"], row["raw_json"]), ("masked-token", '{"demo":true}'))
        self.assertEqual(row["rule_id"], "synthetic-secret-rule")
        self.assertEqual(row["file_path"], "src/app.ts")
        self.assertEqual(row["introduced"], 0)

    def test_default_introduced_is_one(self):
        self.record_finding("semgrep", "vulnerability", {"description": "synthetic"})
        self.assertEqual(self.findings()[0]["introduced"], 1)

    def test_existing_run_short_circuits_even_error_status(self):
        self.assertFalse(self.records["_scanner_already_ran"](self.db, self.case_id, ("semgrep",)))
        self.record_run("semgrep", status="tool_missing")
        self.assertTrue(self.records["_scanner_already_ran"](self.db, self.case_id, ("semgrep",)))

    def test_codeql_cwe_presence_is_required_for_vulnerability_type(self):
        classify = self.records["_codeql_finding_type"]
        self.assertEqual(classify({"cwe": "CWE-79"}), "vulnerability")
        self.assertEqual(classify({"cwe": "    "}), "code_quality")
        self.assertEqual(classify({"severity": "error"}), "code_quality")

    def test_original_clear_codeql_also_removes_other_scanners_vulnerabilities(self):
        self.record_run("codeql", status="ok")
        self.record_run("codeql-head", status="ok")
        self.record_run("semgrep", status="ok")
        self.record_finding("codeql", "code_quality", {"description": "quality"})
        self.record_finding("semgrep", "vulnerability", {"description": "synthetic semgrep"})
        self.assertEqual(len(self.findings()), 2)
        self.records["_clear_scanner"](
            self.db, self.case_id,
            ("codeql", "codeql-base", "codeql-head"),
            ("vulnerability", "code_quality"),
        )
        self.assertEqual(self.findings(), [])
        self.assertIsNone(self.run_row("codeql"))
        self.assertIsNone(self.run_row("codeql-head"))
        self.assertIsNotNone(self.run_row("semgrep"))  # metadata survived, finding did not

    def test_clear_non_codeql_preserves_unrelated_finding_type(self):
        self.record_run("gitleaks")
        self.record_run("dependency-diff")
        self.record_finding("gitleaks", "secret", {"description": "synthetic secret"})
        self.record_finding("dependency-diff", "dependency", {"description": "synthetic dependency"})
        self.records["_clear_scanner"](self.db, self.case_id, ("gitleaks",), ("secret",))
        self.assertEqual([x["finding_type"] for x in self.findings()], ["dependency"])
        self.assertIsNone(self.run_row("gitleaks"))
        self.assertIsNotNone(self.run_row("dependency-diff"))

    def test_direct_scanner_runs_can_close_six_jobs_without_executables(self):
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 6)
        for scanner in (
            "semgrep", "gitleaks", "dependency-diff", "osv-scanner",
            "trivy-scanner", "codeql-base", "codeql-head", "codeql",
        ):
            self.record_run(scanner)
        self.queue["sync_jobs_from_scanner_runs"](self.db, self.case_id)
        rows = self.db.query("SELECT job_type,status FROM scanner_jobs WHERE case_id=?", (self.case_id,))
        self.assertEqual(len(rows), 6)
        self.assertEqual({x["status"] for x in rows}, {"ok"})
        self.queue["update_case_stages"](self.db)
        self.assertEqual(self.case_status()["status"], "scanned_clean")

    def test_error_in_scanner_runs_blocks_original_worker_case(self):
        self.queue["seed_scanner_jobs"](self.db)
        self.record_run("gitleaks", status="error")
        self.queue["sync_jobs_from_scanner_runs"](self.db, self.case_id)
        row = self.db.one(
            "SELECT status FROM scanner_jobs WHERE case_id=? AND job_type='secret_ci'",
            (self.case_id,),
        )
        self.assertEqual(row["status"], "error")
        self.queue["update_case_stages"](self.db)
        self.assertEqual(self.case_status()["status"], "scanner_running")  # other jobs still pending

    def test_original_code_quality_only_finding_still_flags_vulnerability(self):
        self.record_finding("codeql", "code_quality", {
            "introduced": True, "description": "synthetic lint finding",
        })
        self.queue["update_case_stages"](self.db)
        row = self.case_status()
        self.assertEqual(row["status"], "needs_review")
        # Original sync_case_statuses() counts introduced findings of *all* types.
        self.assertEqual(row["downstream_signal"], "vulnerability")
        self.assertNotIn("CodeQL alert introduced", json.loads(row["auto_tags"]))

    def test_not_introduced_finding_does_not_trigger_case_review(self):
        self.record_finding("codeql", "vulnerability", {
            "introduced": False, "cwe": "CWE-999", "description": "pre-existing",
        })
        self.queue["update_case_stages"](self.db)
        self.assertEqual(self.case_status()["status"], "metadata_collected")

    def test_wrong_disposable_db_cannot_be_targeted(self):
        with disposable_original_database() as second:
            with self.assertRaises(TypeError):
                self.records["_insert_run"](
                    second, self.case_id, self.pr_id, "semgrep", "ok",
                )

    def test_modified_historical_runner_fails_before_ast_compilation(self):
        with TemporaryDirectory(prefix="arno_corrupted_scanner_") as folder:
            fake = Path(folder)/"scanner_runner.py"
            fake.write_text("print('UNAUTHORIZED_EXECUTION')\n", encoding="utf-8")
            with mock.patch.object(scanner_contract, "SOURCE_PATH", fake):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    scanner_contract.load_archived_scanner_records(self.db)
