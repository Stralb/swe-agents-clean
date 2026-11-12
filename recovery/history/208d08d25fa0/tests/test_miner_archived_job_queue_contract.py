"""Original worker queue lifecycle in disposable SQLite; scanners not run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from src.pipeline.case_builder import update_case_tags_and_status
from src.pipeline.case_status import sync_case_statuses
from tests.support import archived_job_queue_contract as job


class FrozenCaseStageSourceTests(unittest.TestCase):
    def test_original_status_modules_match_all_three_archives(self):
        root = Path(__file__).resolve().parents[1]
        hashes = {
            "src/pipeline/case_builder.py": "3c2c4e466849ac444d6a5e285c9103ece94bb91cbd5cdf072ef4e64cffa94e38",
            "src/pipeline/case_status.py": "d011c788a5fefc08e5fb56fb8b4baf4a8aae3c4e12ec7a483f1940fb59e46e29",
        }
        for path, expected in hashes.items():
            active = (root / path).read_bytes()
            with self.subTest(path=path):
                self.assertEqual(hashlib.sha256(active).hexdigest(), expected)
                for snap in ("2026-08-17", "2026-08-19", "2026-10-20-live-export"):
                    self.assertEqual(active, (root / "historical/miner" / snap / path).read_bytes())


class OriginalWorkerQueueTests(unittest.TestCase):
    def setUp(self):
        context = disposable_original_database()
        self.db = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.queue = job.load_original_queue(self.db)
        self.repo_id = self.db.insert_or_get_repo({
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
        })
        self.pr_id = self.db.upsert_pr(self.repo_id, {
            "number": 12,
            "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8",
            "body": "Fixes #8",
            "head": {"ref": "codex/fix", "sha": "123"},
            "base": {"ref": "main", "sha": "456"},
        })
        self.issue_id = self.db.upsert_issue(self.repo_id, {
            "number": 8,
            "html_url": "https://example.invalid/example/repo/issues/8",
            "title": "Bug",
            "body": "Please fix the regression in src/runner.ts.",
            "labels": [],
        }, 8, True)
        self.db.link_issue_pr(self.issue_id, self.pr_id, "closing-keyword")
        self.case_id = self.db.create_or_get_case(
            self.repo_id, self.issue_id, self.pr_id,
            "AI-explicit-high", ["AI-explicit-high"],
        )
        self.db.replace_pr_files(self.pr_id, [
            {"filename": "src/runner.ts", "status": "modified", "additions": 2,
             "patch": "@@ -1 +1 @@\n-old\n+new"},
        ])

    def jobs(self):
        return self.db.query(
            "SELECT id, case_id, job_type, status, attempts, priority, worker_id "
            "FROM scanner_jobs ORDER BY priority DESC, id"
        )

    def test_frozen_source_hash_across_three_archives(self):
        original = job.SOURCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), job.SOURCE_SHA256)
        root = Path(__file__).resolve().parents[1]
        for stamp in ("2026-08-17", "2026-08-19", "2026-10-20-live-export"):
            with self.subTest(stamp=stamp):
                self.assertEqual(
                    (root / "historical/miner" / stamp / "src/workers/job_queue.py").read_bytes(),
                    original,
                )

    def test_seed_all_six_workers_without_invoking_a_scanner(self):
        self.assertNotIn("scan_case", self.queue)
        self.assertNotIn("run_scanner_job", self.queue)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 6)
        rows = self.jobs()
        self.assertEqual(
            {r["job_type"] for r in rows},
            {"semgrep_source", "secret_ci", "dependency_downgrade",
             "osv_dependency", "trivy_dependency", "codeql"},
        )
        self.assertTrue(all(r["status"] == "pending" for r in rows))
        self.assertEqual(self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"], "scanner_running")

    def test_seed_is_idempotent(self):
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 6)
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 0)
        self.assertEqual(len(self.jobs()), 6)

    def test_codeql_opt_in_adds_one_job(self):
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db, include_codeql=False), 5)
        self.assertNotIn("codeql", {row["job_type"] for row in self.jobs()})
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db, include_codeql=True), 1)

    def test_worker_claim_priority_and_attempts(self):
        self.queue["seed_scanner_jobs"](self.db)
        job_record = self.queue["claim_job"](self.db, ["codeql", "semgrep_source"], worker_id="synthetic-worker")
        self.assertEqual(job_record.job_type, "semgrep_source")
        self.assertEqual(job_record.attempts, 1)
        row = self.db.one("SELECT status, worker_id, attempts FROM scanner_jobs WHERE id=?", (job_record.id,))
        self.assertEqual(row["status"], "running")
        self.assertEqual(row["worker_id"], "synthetic-worker")
        self.assertEqual(row["attempts"], 1)
        self.assertEqual(self.queue["claim_job"](self.db, ["semgrep_source"], worker_id="other"), None)

    def test_finish_job_and_case_stage(self):
        self.queue["seed_scanner_jobs"](self.db)
        for row in self.jobs():
            self.queue["finish_job"](self.db, row["id"], "ok")
        self.queue["update_case_stages"](self.db)
        self.assertEqual(self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"], "scanned_clean")

    def test_original_not_applicable_outcome_is_blocked(self):
        self.queue["seed_scanner_jobs"](self.db)
        rows = self.jobs()
        for row in rows:
            self.queue["finish_job"](self.db, row["id"], "not_applicable" if row["job_type"] == "codeql" else "ok")
        self.queue["update_case_stages"](self.db)
        self.assertEqual(
            self.db.one("SELECT status FROM cases WHERE id=?", (self.case_id,))["status"],
            "scan_blocked",
        )

    def test_original_retry_reset_changes_only_disposable_rows(self):
        self.queue["seed_scanner_jobs"](self.db)
        picked = self.queue["claim_job"](self.db, ["semgrep_source"], worker_id="synthetic")
        self.assertEqual(self.queue["reset_running_jobs_on_start"](self.db, job_types=["semgrep_source"]), 1)
        row = self.db.one("SELECT status, worker_id FROM scanner_jobs WHERE id=?", (picked.id,))
        self.assertEqual((row["status"], row["worker_id"]), ("pending", None))
        self.assertEqual(self.queue["claim_job"](self.db, ["semgrep_source"], worker_id="second").attempts, 2)

    def test_heartbeat_upserts_single_worker(self):
        self.queue["heartbeat"](self.db, "worker-01", "source", "evaluate", "running", "starting")
        self.queue["heartbeat"](self.db, "worker-01", "source", "evaluate", "idle", "completed")
        row = self.db.one("SELECT status, detail FROM worker_heartbeats WHERE worker_id=?", ("worker-01",))
        self.assertEqual((row["status"], row["detail"]), ("idle", "completed"))
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM worker_heartbeats")["n"], 1)

    def test_config_for_job_is_pure_and_copies_input(self):
        cfg = {"scanners": {"codeql": True, "semgrep": True}, "cache": {"force_rescan": False}}
        for kind, name in [("secret_ci", "gitleaks"), ("codeql", "codeql"), ("semgrep_source", "semgrep")]:
            with self.subTest(kind=kind):
                answer = self.queue["_scanner_config_for_job"](self.db, cfg, kind)
                self.assertTrue(answer["scanners"][name])
                self.assertEqual(cfg["scanners"]["codeql"], True)
                self.assertEqual(cfg["cache"]["force_rescan"], False)

    def test_reviewed_cases_are_not_seeded(self):
        self.db.execute("UPDATE cases SET status='reviewed' WHERE id=?", (self.case_id,))
        self.assertEqual(self.queue["seed_scanner_jobs"](self.db), 0)
        self.assertEqual(self.jobs(), [])

    def test_introduced_finding_sets_needs_review_without_scanner_invocation(self):
        self.db.execute(
            "INSERT INTO scanner_findings(case_id, pr_id, scanner, finding_type, introduced) "
            "VALUES (?, ?, 'codeql', 'vulnerability', 1)",
            (self.case_id, self.pr_id),
        )
        update_case_tags_and_status(self.db)
        sync_case_statuses(self.db)
        row = self.db.one("SELECT status, auto_tags FROM cases WHERE id=?", (self.case_id,))
        self.assertEqual(row["status"], "needs_review")
        self.assertIn("CodeQL alert introduced", json.loads(row["auto_tags"]))

    def test_source_corruption_rejected_before_execution(self):
        with TemporaryDirectory(prefix="arno_worker_fixture_bad_") as d:
            altered = Path(d) / "job_queue.py"
            altered.write_text("print('SHOULD_NEVER_RUN')\n", encoding="utf-8")
            with mock.patch.object(job, "SOURCE_PATH", altered):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    job.load_original_queue(self.db)

    def test_wrong_database_cannot_execute_queue_operations(self):
        with disposable_original_database() as separate:
            with self.assertRaises(TypeError):
                self.queue["seed_scanner_jobs"](separate)

    def test_no_path_or_process_services_in_extracted_namespace(self):
        self.assertNotIn("run_scanner_job", self.queue)
        self.assertNotIn("scan_case", self.queue)
        self.assertNotIn("evaluate_loop", self.queue)
        self.assertNotIn("submit_slurm", self.queue)
