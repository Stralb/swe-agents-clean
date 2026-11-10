"""Opt-in real Gitleaks smoke: exact original wrapper, synthetic patch only.

This is never exercised by the ordinary offline CI suite. The pinned release
archive must be SHA-256 verified by the dedicated GitHub Actions workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from tests.support.archived_gitleaks_process import load_original_gitleaks_process
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import ArchivedFixtureWorker, FixtureWorkerSettings
from tests.support.archived_job_queue_contract import load_original_queue
from src.db.disposable_harness import disposable_original_database

_VERSION = "8.30.1"
_SYNTHETIC_TOKEN = "ZQ8L2W9R4N7T5Y3K6P1S0V25"
_CONFIG = r"""
[[rules]]
id = "arno-synthetic-smoke"
description = "Synthetic detector rule, never a real credential"
regex = '''SYNTHETIC_SMOKE_KEY\s*=\s*"([A-Z0-9]{24})"'''
secretGroup = 1
"""


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_PINNED_GITLEAKS") == "1",
    "Requires checksum-verified Gitleaks from dedicated isolated smoke workflow",
)
class RealGitleaksSyntheticOnlyTests(unittest.TestCase):
    def test_exact_original_wrapper_runs_pinned_real_gitleaks_on_temp_fixture_only(self):
        executable = Path(os.environ["ARNO_GITLEAKS_EXECUTABLE"]).resolve()
        self.assertEqual(executable.name, "gitleaks")
        self.assertTrue(executable.is_file())
        self.assertEqual(len(_SYNTHETIC_TOKEN), 24)

        with TemporaryDirectory(prefix="arno_real_gitleaks_synthetic_") as td:
            config = Path(td) / "synthetic_gitleaks.toml"
            config.write_text(_CONFIG, encoding="utf-8")
            version = subprocess.run(
                [str(executable), "version"],
                cwd=td,
                capture_output=True, text=True, check=True, timeout=10,
            )
            self.assertIn(_VERSION, version.stdout + version.stderr)
            path = str(executable.parent) + os.pathsep + "/usr/bin:/bin"
            with mock.patch.dict(os.environ, {
                "PATH": path,
                "GITLEAKS_CONFIG": str(config),
            }):
                self.assertEqual(
                    Path(shutil.which("gitleaks") or "").resolve(), executable
                )
                scan = load_original_gitleaks_process()
                findings, meta = scan([{
                    "filename": "fixture/app.ts",
                    "patch": (
                        "@@ -0,0 +1 @@\n"
                        '+SYNTHETIC_SMOKE_KEY = "' + _SYNTHETIC_TOKEN + '"\n'
                    ),
                }])

            self.assertEqual(meta["status"], "ok", meta)
            self.assertTrue(findings, (meta, findings))
            found = [f for f in findings if f.get("rule") == "arno-synthetic-smoke"]
            self.assertEqual(len(found), 1, (meta, findings))
            self.assertTrue(str(found[0].get("file")).endswith("fixture/app.ts"))
            self.assertNotIn(_SYNTHETIC_TOKEN, repr(findings))


    def test_real_binary_flows_through_original_worker_scanner_and_disposable_database(self):
        """Real CLI, fabricated code patch, original job dispatch and original DB writes."""
        executable = Path(os.environ["ARNO_GITLEAKS_EXECUTABLE"]).resolve()
        self.assertEqual(executable.name, "gitleaks")
        self.assertTrue(executable.is_file())
        with TemporaryDirectory(prefix="arno_real_gitleaks_worker_") as td:
            config = Path(td) / "synthetic_gitleaks.toml"
            config.write_text(_CONFIG, encoding="utf-8")

            class SyntheticOnlyRealGitleaksProvider(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.invocations = 0

                def scan_files_with_gitleaks(self, files):
                    if (
                        len(files) != 1
                        or files[0]["filename"] != "fixture/app.ts"
                        or _SYNTHETIC_TOKEN not in (files[0].get("patch") or "")
                    ):
                        raise AssertionError("Refuse any non-synthetic Gitleaks input")
                    self.invocations += 1
                    return load_original_gitleaks_process()(files)

            with disposable_original_database() as db:
                repo = db.insert_or_get_repo({
                    "full_name": "fixture/repo",
                    "html_url": "https://example.invalid/fixture/repo",
                })
                pr = db.upsert_pr(repo, {
                    "number": 1, "html_url": "https://example.invalid/fixture/repo/pull/1",
                    "head": {"ref": "synthetic", "sha": "synthetic-head"},
                    "base": {"ref": "main", "sha": "synthetic-base"},
                })
                issue = db.upsert_issue(repo, {
                    "number": 2,
                    "html_url": "https://example.invalid/fixture/repo/issues/2",
                    "title": "Synthetic worker smoke",
                    "body": "Run only a fabricated fixture",
                    "labels": [],
                }, 5, True)
                db.link_issue_pr(issue, pr, "synthetic-only")
                case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
                db.replace_pr_files(pr, [{
                    "filename": "fixture/app.ts", "category": "source",
                    "status": "added", "additions": 1, "deletions": 0,
                    "patch": (
                        "@@ -0,0 +1 @@\n"
                        '+SYNTHETIC_SMOKE_KEY = "' + _SYNTHETIC_TOKEN + '"\n'
                    ),
                }])
                queue = load_original_queue(db)
                self.assertEqual(queue["seed_scanner_jobs"](db), 6)
                claimed = queue["claim_job"](
                    db, ["secret_ci"], worker_id="synthetic-real-gitleaks"
                )
                self.assertIsNotNone(claimed)
                provider = SyntheticOnlyRealGitleaksProvider()
                worker = ArchivedFixtureWorker(db, provider)
                flags = {
                    "gitleaks": False, "dependency_downgrade": False,
                    "osv": False, "trivy": False,
                    "semgrep": False, "codeql": False,
                }
                with mock.patch.dict(os.environ, {
                    "PATH": str(executable.parent) + os.pathsep + "/usr/bin:/bin",
                    "GITLEAKS_CONFIG": str(config),
                }):
                    self.assertEqual(
                        Path(shutil.which("gitleaks") or "").resolve(), executable
                    )
                    worker.run(claimed, FixtureWorkerSettings({
                        "scanners": flags, "cache": {"force_rescan": False},
                    }))
                self.assertEqual(provider.invocations, 1)
                job = db.one(
                    "SELECT status,attempts FROM scanner_jobs WHERE id=?", (claimed.id,)
                )
                self.assertEqual((job["status"], job["attempts"]), ("ok", 1))
                scan = db.one(
                    "SELECT scanner,status FROM scanner_runs WHERE case_id=?", (case_id,)
                )
                self.assertEqual((scan["scanner"], scan["status"]), ("gitleaks", "ok"))
                findings = db.query(
                    "SELECT scanner,finding_type,rule_id,evidence,raw_json,introduced "
                    "FROM scanner_findings WHERE case_id=?", (case_id,)
                )
                self.assertEqual(len(findings), 1, findings)
                finding = findings[0]
                self.assertEqual(
                    (finding["scanner"], finding["finding_type"], finding["rule_id"], finding["introduced"]),
                    ("gitleaks", "secret", "arno-synthetic-smoke", 1),
                )
                self.assertNotIn(_SYNTHETIC_TOKEN, repr(finding))
                self.assertEqual(
                    db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                    "needs_review",
                )


if __name__ == "__main__":
    unittest.main()
