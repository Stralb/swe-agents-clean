"""Run exact archived claim -> dispatcher -> scanner -> finish paths offline."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import socket
import subprocess
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import (
    FixtureScannerProviders, MissingScannerFixture,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)


def fixture_config():
    return {
        "scanners": {
            "gitleaks": False, "dependency_downgrade": False,
            "osv": False, "trivy": False, "semgrep": False, "codeql": False,
        },
        "cache": {"force_rescan": False},
    }


class ExactArchivedWorkerDispatchTests(unittest.TestCase):
    def setUp(self):
        ctx = disposable_original_database()
        self.db = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        repo = self.db.insert_or_get_repo({
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
        })
        pr = self.db.upsert_pr(repo, {
            "number": 18,
            "html_url": "https://example.invalid/example/repo/pull/18",
            "head": {"ref": "synthetic", "sha": "synthetic-head"},
            "base": {"ref": "main", "sha": "synthetic-base"},
        })
        issue = self.db.upsert_issue(repo, {
            "number": 7, "html_url": "https://example.invalid/example/repo/issues/7",
            "title": "Synthetic issue", "body": "Please fix this synthetic bug",
            "labels": [],
        }, 5, True)
        self.db.link_issue_pr(issue, pr, "synthetic")
        self.case_id = self.db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
        self.db.replace_pr_files(pr, [
            {
                "filename": "src/fixture.ts", "category": "source",
                "status": "modified", "additions": 1, "deletions": 1,
                "patch": "@@ -1 +1 @@\n-old\n+new\n",
            },
            {
                "filename": "requirements.txt", "category": "dependency",
                "status": "modified", "additions": 1, "deletions": 1,
                "patch": "@@ -1 +1 @@\n-fixture==1.0\n+fixture==2.0\n",
            },
        ])
        self.queue = load_original_queue(self.db)
        self.settings = FixtureWorkerSettings(fixture_config())

    def job_rows(self):
        return self.db.query(
            "SELECT job_type,status,attempts,worker_id FROM scanner_jobs ORDER BY priority DESC, id"
        )

    def claim(self, job_types=None):
        return self.queue["claim_job"](
            self.db,
            job_types or list(self.queue["REQUIRED_JOB_TYPES"]),
            worker_id="fixture-worker",
        )

    def dispatch(self, worker, job):
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network")):
            with mock.patch.object(subprocess, "run", side_effect=AssertionError("scanner binary")):
                worker.run(job, self.settings)

    def test_all_six_original_worker_paths_complete_through_original_scanners(self):
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 6)
        backend = FixtureScannerProviders(
            gitleaks=[([], {"status": "ok"})],
            dependency_diff=[[]],
            osv=[([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"})],
            trivy=[([], {"status": "ok"}, {"status": "ok"}, {"status": "ok"})],
            semgrep=[([], {"status": "ok"})],
            codeql={
                "synthetic-base": ([], {"status": "ok"}),
                "synthetic-head": ([], {"status": "ok"}),
            },
        )
        worker = ArchivedFixtureWorker(self.db, backend)
        claimed = []
        while True:
            job = self.claim()
            if job is None:
                break
            claimed.append(job.job_type)
            self.dispatch(worker, job)
        self.assertEqual(claimed, [
            "semgrep_source", "secret_ci", "dependency_downgrade",
            "osv_dependency", "trivy_dependency", "codeql",
        ])
        self.assertEqual({r["status"] for r in self.job_rows()}, {"ok"})
        self.assertTrue(all(r["attempts"] == 1 for r in self.job_rows()))
        self.assertEqual(
            self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"],
            "scanned_clean",
        )
        names = [r["scanner"] for r in self.db.query(
            "SELECT scanner FROM scanner_runs WHERE case_id=? ORDER BY id", (self.case_id,)
        )]
        self.assertEqual(names, [
            "semgrep", "gitleaks", "dependency-diff",
            "osv-base", "osv-head", "osv-scanner",
            "trivy-base", "trivy-head", "trivy-scanner",
            "codeql-javascript-typescript-base",
            "codeql-javascript-typescript-head",
            "codeql-base", "codeql-head", "codeql",
        ])
        self.assertEqual(len(backend.calls), 7)

    def test_worker_error_scan_is_not_reported_as_clean(self):
        self.queue["seed_scanner_jobs"](self.db)
        job = self.claim(["semgrep_source"])
        worker = ArchivedFixtureWorker(self.db, FixtureScannerProviders(
            semgrep=[([], {"status": "error", "stderr": "synthetic failure"})],
        ))
        self.dispatch(worker, job)
        row = self.db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))
        self.assertEqual(row["status"], "error")
        self.assertNotEqual(
            self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"],
            "scanned_clean",
        )

    def test_missing_fixture_is_unresolved_and_worker_can_retry(self):
        self.queue["seed_scanner_jobs"](self.db)
        job = self.claim(["secret_ci"])
        worker = ArchivedFixtureWorker(self.db, FixtureScannerProviders())
        with self.assertRaises(MissingScannerFixture):
            self.dispatch(worker, job)
        self.assertEqual(
            self.db.one("SELECT status FROM scanner_jobs WHERE id=?", (job.id,))["status"],
            "running",
        )
        self.assertEqual(self.queue["reset_running_jobs_on_start"](
            self.db, job_types=["secret_ci"]), 1)
        retry = self.claim(["secret_ci"])
        self.assertEqual(retry.attempts, 2)
        resumed = ArchivedFixtureWorker(self.db, FixtureScannerProviders(
            gitleaks=[([], {"status": "ok"})],
        ))
        self.dispatch(resumed, retry)
        self.assertEqual(
            self.db.one("SELECT status FROM scanner_jobs WHERE id=?", (retry.id,))["status"],
            "ok",
        )

    def test_refuses_unclaimed_job_and_wrong_settings(self):
        self.queue["seed_scanner_jobs"](self.db)
        picked = self.claim(["secret_ci"])
        worker = ArchivedFixtureWorker(self.db, FixtureScannerProviders())
        with self.assertRaises(TypeError):
            worker.run(picked, fixture_config())
        with self.assertRaises(ValueError):
            worker.run(picked, FixtureWorkerSettings({"github_token": "secret"}))
        with self.assertRaises(ValueError):
            worker.run(picked, FixtureWorkerSettings({"scanners": {"gitleaks": True}}))
        self.queue["finish_job"](self.db, picked.id, "ok")
        with self.assertRaises(ValueError):
            worker.run(picked, self.settings)

    def test_refuses_non_synthetic_case_before_running(self):
        self.queue["seed_scanner_jobs"](self.db)
        picked = self.claim(["secret_ci"])
        self.db.execute(
            "UPDATE repos SET html_url=? WHERE full_name='example/repo'",
            ("https://github.com/real/sensitive",),
        )
        worker = ArchivedFixtureWorker(self.db, FixtureScannerProviders())
        with self.assertRaises(ValueError):
            worker.run(picked, self.settings)
        self.assertEqual(
            self.db.one("SELECT status FROM scanner_jobs WHERE id=?", (picked.id,))["status"],
            "running",
        )

    def test_atomic_claims_never_assign_same_job_to_two_workers(self):
        self.queue["seed_scanner_jobs"](self.db)
        def claim_one(number):
            return self.queue["claim_job"](
                self.db, list(self.queue["REQUIRED_JOB_TYPES"]),
                worker_id=f"fixture-{number}",
            )
        with ThreadPoolExecutor(max_workers=6) as executor:
            claims = list(executor.map(claim_one, range(12)))
        claims = [job for job in claims if job is not None]
        self.assertEqual(len(claims), 6)
        self.assertEqual(len({job.id for job in claims}), 6)
        self.assertEqual(len({job.job_type for job in claims}), 6)
        self.assertEqual({r["status"] for r in self.job_rows()}, {"running"})


if __name__ == "__main__":
    unittest.main()
