"""Exact historical Gitleaks materialization and shell invocation, stub only."""
from __future__ import annotations

from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from tests.support import archived_gitleaks_process as source


class ArchivedGitleaksProcessTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = source.DisposableGitleaksProcess()

    def invoke(self, files):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            return self.pipeline.run(files)

    def test_real_original_shell_invokes_fixture_executable_and_reads_sarif_like_report(self):
        findings, meta = self.invoke([{
            "filename": "fixture/app.ts",
            "patch": "@@ -1 +1 @@\n-old\n+SYNTHETIC_KEY_SIGNAL = 'Z1'\n",
        }])
        self.assertEqual(meta["status"], "ok")
        self.assertIn("synthetic-stub completed", meta["stdout"])
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual((finding["file"], finding["line"], finding["rule"]),
                         ("fixture/app.ts", 1, "synthetic-rule"))
        self.assertEqual(finding["evidence"], "<redacted by gitleaks>")
        self.assertEqual(finding["raw"]["Match"], "<redacted>")

    def test_historical_status_is_ok_if_report_exists_even_when_cli_returns_one(self):
        findings, meta = self.invoke([{
            "filename": "fixture/app.ts",
            "patch": "@@ -0,0 +1 @@\n+SYNTHETIC_KEY_SIGNAL = 'Z2'\n",
        }])
        self.assertTrue(findings)
        self.assertEqual(meta["status"], "ok")

    def test_original_excludes_placeholder_evidence_after_stub_report(self):
        findings, meta = self.invoke([{
            "filename": "fixture/app.ts",
            "patch": "@@ -0,0 +1 @@\n+SYNTHETIC_KEY_SIGNAL = 'fake-placeholder'\n",
        }])
        self.assertEqual(meta["status"], "ok")
        self.assertEqual(findings, [])

    def test_baseline_file_skips_cli_and_returns_not_applicable(self):
        findings, meta = self.invoke([{
            "filename": "fixture/.secrets.baseline",
            "patch": "@@ -0,0 +1 @@\n+SYNTHETIC_KEY_SIGNAL\n",
        }])
        self.assertEqual(findings, [])
        self.assertEqual(meta["status"], "not_applicable")

    def test_deletions_only_skip_cli(self):
        findings, meta = self.invoke([{
            "filename": "fixture/app.ts",
            "patch": "@@ -1 +0,0 @@\n-SYNTHETIC_KEY_SIGNAL\n",
        }])
        self.assertEqual(findings, [])
        self.assertEqual(meta["status"], "not_applicable")

    def test_no_report_and_nonzero_cli_returns_error(self):
        findings, meta = self.invoke([{
            "filename": "fixture/app.ts",
            "patch": "@@ -0,0 +1 @@\n+SYNTHETIC_FAIL_NO_REPORT\n",
        }])
        self.assertEqual(findings, [])
        self.assertEqual(meta["status"], "error")
        self.assertIn("Synthetic CLI failure", meta["stderr"])

    def test_refuses_any_out_of_scope_file_or_patch_before_process(self):
        for row in [
            {"filename": "../secret.txt", "patch": "+SYNTHETIC_KEY_SIGNAL"},
            {"filename": "fixture/../../secret.txt", "patch": "+SYNTHETIC_KEY_SIGNAL"},
            {"filename": "src/production.ts", "patch": "+SYNTHETIC_KEY_SIGNAL"},
            {"filename": "fixture/app.ts", "patch": "+production-secrets"},
        ]:
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    self.invoke([row])

    def test_hash_mismatch_rejects_scanner_before_ast_execution(self):
        with TemporaryDirectory(prefix="arno_bad_gitleaks_") as td:
            replacement = Path(td) / "gitleaks_scanner.py"
            replacement.write_text("print('SHOULD NOT RUN')\n", encoding="utf-8")
            with mock.patch.object(source, "GITLEAKS_PATH", replacement):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    source.load_original_gitleaks_process()

    def test_hash_mismatch_rejects_original_shell_before_execution(self):
        with TemporaryDirectory(prefix="arno_bad_shell_") as td:
            replacement = Path(td) / "shell.py"
            replacement.write_text("print('SHOULD NOT RUN')\n", encoding="utf-8")
            with mock.patch.object(source, "SHELL_PATH", replacement):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    source.load_original_gitleaks_process()


if __name__ == "__main__":
    unittest.main()
