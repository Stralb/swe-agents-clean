"""Actual OSV engine matched against an offline fabricated advisory through the
exact historical base/head Git snapshot + worker + SQLite pipeline.
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
from tests.support.archived_real_osv_snapshot import (
    ADVISORY, FILE, REPO_URL, RealOfflineOSVSnapshot,
)


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_REAL_DEPENDENCY_ENGINES") == "1",
    "Requires checksum-verified OSV candidate and no-network runtime",
)
class RealOSVOriginalSnapshotAndWorkerTests(unittest.TestCase):
    def test_genuine_osv_base_head_and_original_advisory_delta(self):
        with RealOfflineOSVSnapshot() as replay:
            findings, summary, base, head = replay.run(
                REPO_URL, replay.base_sha, replay.head_sha, replay.files()
            )
            self.assertEqual(
                (base["status"], head["status"], summary["status"]),
                ("ok", "ok", "ok"), (summary, base, head),
            )
            self.assertEqual(len(findings), 1, (findings, summary, base, head))
            self.assertEqual(findings[0]["vuln_id"], ADVISORY)
            self.assertEqual(findings[0]["file"], FILE)
            self.assertEqual(
                (findings[0]["diff_linked"], findings[0]["change_type"]),
                (True, "introduced_vulnerable_dependency"),
            )
            self.assertEqual(
                (json.loads(base["stdout"])["finding_count"],
                 json.loads(head["stdout"])["finding_count"]),
                (0, 1),
            )
            self.assertEqual(
                (replay.commands.count("git"), replay.commands.count("osv-scanner")),
                (7, 2),
            )

    def test_original_queue_to_genuine_osv_to_disposable_scanner_tables(self):
        with RealOfflineOSVSnapshot() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/real-offline-osv-snapshots",
                "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 7,
                "html_url": REPO_URL + "/pull/7",
                "base": {"ref": "main", "sha": replay.base_sha},
                "head": {"ref": "fabricated", "sha": replay.head_sha},
            })
            issue = db.upsert_issue(repo, {
                "number": 6,
                "html_url": REPO_URL + "/issues/6",
                "title": "Fabricated dependency downgrade",
                "body": "Synthetic offline advisory and no target project",
                "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "fixture")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class StrictBackend(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.actual_runs = 0

                def scan_dependency_snapshots(
                    self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
                ):
                    normalized = [
                        {k: f[k] for k in (
                            "filename", "category", "status",
                            "patch", "additions", "deletions",
                        )}
                        for f in files
                    ]
                    self.actual_runs += 1
                    return replay.run(
                        repo_url, base_sha, head_sha, normalized,
                        timeout_seconds=timeout_seconds,
                    )

            q = load_original_queue(db)
            self.assertEqual(q["seed_scanner_jobs"](db), 6)
            job = q["claim_job"](
                db, ["osv_dependency"], worker_id="real-osv-synthetic-only",
            )
            backend = StrictBackend()
            ArchivedFixtureWorker(db, backend).run(
                job, FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False,
                        "semgrep": False, "codeql": False,
                    },
                    "cache": {"force_rescan": False},
                }),
            )
            self.assertEqual(backend.actual_runs, 1)
            self.assertEqual(
                db.one(
                    "SELECT status FROM scanner_jobs WHERE id=?", (job.id,),
                )["status"],
                "ok",
            )
            scan_runs = db.query(
                "SELECT scanner,status FROM scanner_runs WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual(
                [(x["scanner"], x["status"]) for x in scan_runs],
                [("osv-base", "ok"), ("osv-head", "ok"), ("osv-scanner", "ok")],
            )
            finding = db.one(
                "SELECT scanner,finding_type,rule_id,introduced,raw_json "
                "FROM scanner_findings WHERE case_id=?", (case_id,),
            )
            self.assertEqual(
                (finding["scanner"], finding["finding_type"],
                 finding["rule_id"], finding["introduced"]),
                ("osv-scanner", "dependency", ADVISORY, 1),
            )
            self.assertEqual(
                json.loads(finding["raw_json"])["id"], ADVISORY,
            )
            self.assertEqual(
                db.one("SELECT status FROM cases WHERE id=?", (case_id,))["status"],
                "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
