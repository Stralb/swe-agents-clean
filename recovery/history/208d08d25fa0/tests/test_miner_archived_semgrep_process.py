"""Exact archived Semgrep original scanner, Git checkout, and diff linking.

The ordinary test suite runs only a deterministic local stub. Real Semgrep is
tested separately by an opt-in, version-pinned CI job.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support import archived_semgrep_process as semgrep


class ExactArchivedSemgrepProcessTests(unittest.TestCase):
    def test_original_git_clone_checkout_semgrep_cli_and_diff_filtering(self):
        with semgrep.LocalSemgrepReplay() as replay:
            findings, meta = replay.scan(
                semgrep.REPO_URL, replay.head_sha, replay.synthetic_files(),
            )
            self.assertEqual(meta["status"], "ok", meta)
            self.assertEqual(len(findings), 2, (meta, findings))
            by_file = {x["file"]: x for x in findings}
            self.assertEqual(set(by_file), set(semgrep.SOURCE_NAMES))
            promoted = by_file["src/app.py"]
            filtered = by_file["tests/test_fixture.py"]
            self.assertEqual(
                (promoted["finding_type"], promoted["introduced"],
                 promoted["promoted"], promoted["diff_linked"]),
                ("vulnerability", 1, True, True),
            )
            self.assertEqual(
                (filtered["finding_type"], filtered["introduced"],
                 filtered["promoted"], filtered["rejection_reasons"]),
                ("semgrep_filtered", 0, False, ["test_or_example_path"]),
            )
            self.assertIn("all_findings=2", meta["stdout"])
            self.assertIn("promoted=1 filtered=1", meta["stdout"])
            self.assertEqual(
                [c[0] for c in replay.calls],
                ["git", "git", "git", "semgrep"],
            )

    def test_fails_closed_for_missing_or_non_synthetic_git_identity(self):
        with semgrep.LocalSemgrepReplay() as replay:
            with self.assertRaises(ValueError):
                replay.scan("https://github.com/sensitive/repository",
                            replay.head_sha, replay.synthetic_files())
            with self.assertRaises(ValueError):
                replay.scan(semgrep.REPO_URL, "unknown-sha", replay.synthetic_files())
            with self.assertRaises(ValueError):
                replay.scan(semgrep.REPO_URL, replay.head_sha, [{
                    "filename": "../user.py", "patch": semgrep.ADDED_PATCH,
                }])
            self.assertEqual(replay.calls, [])

    def test_original_semgrep_version_hash_guard_rejects_altered_source(self):
        with TemporaryDirectory(prefix="arno_bad_semgrep_") as td:
            bad = Path(td) / "semgrep_scanner.py"
            bad.write_text("print('UNAUTHORIZED')\n", encoding="utf-8")
            with mock.patch.object(semgrep, "SOURCE_PATH", bad):
                with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                    semgrep.load_original_semgrep_scan(lambda *_a, **_kw: None)

    def test_worker_dispatch_and_disposable_sqlite_capture_filtered_and_promoted(self):
        with semgrep.LocalSemgrepReplay() as replay:
            with disposable_original_database() as db:
                repo = db.insert_or_get_repo({
                    "full_name": "fixture/local-semgrep",
                    "html_url": semgrep.REPO_URL,
                })
                pr = db.upsert_pr(repo, {
                    "number": 9, "html_url": semgrep.REPO_URL + "/pull/9",
                    "head": {"ref": "synthetic", "sha": replay.head_sha},
                    "base": {"ref": "main", "sha": replay.head_sha},
                })
                issue = db.upsert_issue(repo, {
                    "number": 8, "html_url": semgrep.REPO_URL + "/issues/8",
                    "title": "Synthetic audit", "body": "Run local fixtures only",
                    "labels": [],
                }, 4, True)
                db.link_issue_pr(issue, pr, "synthetic")
                case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
                db.replace_pr_files(pr, replay.synthetic_files())

                class RestrictedProvider(FixtureScannerProviders):
                    def __init__(self):
                        super().__init__()
                        self.calls_to_real_wrapper = 0

                    def scan_head_with_semgrep(
                        self, repo_url, head_sha, files, *,
                        semgrep_config, timeout_seconds,
                    ):
                        if semgrep_config != str(replay.rule_file):
                            raise AssertionError("Unapproved fixture rule file")
                        self.calls_to_real_wrapper += 1
                        return replay.scan(
                            repo_url, head_sha,
                            [{k: f[k] for k in ("filename", "status",
                                               "patch", "additions", "deletions")}
                             for f in files],
                            timeout_seconds=timeout_seconds,
                        )

                queue = load_original_queue(db)
                self.assertEqual(queue["seed_scanner_jobs"](db), 6)
                claimed = queue["claim_job"](
                    db, ["semgrep_source"], worker_id="synthetic-semgrep-worker",
                )
                provider = RestrictedProvider()
                settings = FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False,
                        "semgrep": False, "codeql": False,
                        "semgrep_config": str(replay.rule_file),
                    },
                    "cache": {"force_rescan": False},
                })
                ArchivedFixtureWorker(db, provider).run(claimed, settings)
                self.assertEqual(provider.calls_to_real_wrapper, 1)
                self.assertEqual(
                    db.one("SELECT status FROM scanner_jobs WHERE id=?", (claimed.id,))["status"],
                    "ok",
                )
                finding_rows = db.query(
                    "SELECT file_path,scanner,finding_type,introduced FROM scanner_findings "
                    "WHERE case_id=? ORDER BY file_path", (case_id,),
                )
                self.assertEqual(len(finding_rows), 2, finding_rows)
                by_path = {x["file_path"]: x for x in finding_rows}
                self.assertEqual(
                    (by_path["src/app.py"]["finding_type"], by_path["src/app.py"]["introduced"]),
                    ("vulnerability", 1),
                )
                self.assertEqual(
                    (by_path["tests/test_fixture.py"]["finding_type"],
                     by_path["tests/test_fixture.py"]["introduced"]),
                    ("semgrep_filtered", 0),
                )
                self.assertEqual(
                    db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                    "needs_review",
                )


if __name__ == "__main__":
    unittest.main()
