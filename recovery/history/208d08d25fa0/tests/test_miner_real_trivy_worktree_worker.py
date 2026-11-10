"""Full archived Git worktree + real Trivy OCI DB + worker/SQLite replay.

Opt-in CI only; scanner network namespace is disabled. All repository source
content is fixed, harmless PyPI requirements generated into /tmp.
"""
from __future__ import annotations

import json
import os
import unittest

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_real_trivy_snapshot import (
    FILENAME, REPO_URL, RealFrozenTrivySnapshot,
)


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_PINNED_TRIVY_DB") == "1",
    "Requires real checksum-verified Trivy and frozen offline OCI DB",
)
class RealTrivyOriginalWorktreeAndWorkerTests(unittest.TestCase):
    def test_original_git_base_head_real_trivy_frozen_advisory_delta(self):
        with RealFrozenTrivySnapshot() as replay:
            findings, summary, base, head = replay.run(
                REPO_URL, replay.base_sha, replay.head_sha, replay.files()
            )
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "ok", "ok"), (summary, base, head),
            )
            self.assertTrue(findings, (summary, base, head))
            self.assertTrue(
                all(f["introduced"] == 1 and f["diff_linked"] for f in findings),
            )
            self.assertTrue(
                all(f["file"] == FILENAME for f in findings), findings
            )
            metrics = json.loads(summary["stdout"])
            self.assertGreater(metrics["head_findings"], 0)
            self.assertGreater(metrics["introduced"], 0)
            self.assertEqual(
                replay.calls,
                ["trivy", "git", "git", "git", "git", "git", "trivy", "trivy"],
            )

    def test_full_original_worker_and_sqlite_receive_real_trivy_findings(self):
        with RealFrozenTrivySnapshot() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/real-frozen-trivy-snapshots",
                "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 18, "html_url": REPO_URL + "/pull/18",
                "base": {"ref": "main", "sha": replay.base_sha},
                "head": {"ref": "synthetic", "sha": replay.head_sha},
            })
            issue = db.upsert_issue(repo, {
                "number": 17, "html_url": REPO_URL + "/issues/17",
                "title": "Fabricated manifest regression",
                "body": "Use only public release versions of requests",
                "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "synthetic")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class StrictRealBackend(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.real_calls = 0

                def scan_dependency_snapshots_with_trivy(
                    self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
                ):
                    reduced = [
                        {field: item[field] for field in (
                            "filename", "status", "category",
                            "patch", "additions", "deletions",
                        )}
                        for item in files
                    ]
                    self.real_calls += 1
                    return replay.run(
                        repo_url, base_sha, head_sha, reduced,
                        timeout_seconds=timeout_seconds,
                    )

            queue = load_original_queue(db)
            self.assertEqual(queue["seed_scanner_jobs"](db), 6)
            job = queue["claim_job"](
                db, ["trivy_dependency"], worker_id="real-trivy-synthetic",
            )
            provider = StrictRealBackend()
            ArchivedFixtureWorker(db, provider).run(
                job, FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False,
                        "semgrep": False, "codeql": False,
                    },
                    "cache": {"force_rescan": False},
                }),
            )
            self.assertEqual(provider.real_calls, 1)
            self.assertEqual(
                db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))["status"],
                "ok",
            )
            rows = db.query(
                "SELECT scanner,status FROM scanner_runs WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual(
                [(r["scanner"], r["status"]) for r in rows],
                [("trivy-base", "ok"), ("trivy-head", "ok"), ("trivy-scanner", "ok")],
            )
            findings = db.query(
                "SELECT scanner,finding_type,rule_id,introduced,raw_json "
                "FROM scanner_findings WHERE case_id=?", (case_id,),
            )
            self.assertGreater(len(findings), 0)
            self.assertTrue(all(
                f["scanner"] == "trivy-scanner"
                and f["finding_type"] == "dependency"
                and f["introduced"] == 1
                and bool(f["rule_id"])
                for f in findings
            ), findings)
            self.assertTrue(any(
                "requests" in str(f["raw_json"]).lower() for f in findings
            ))
            self.assertEqual(
                db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
