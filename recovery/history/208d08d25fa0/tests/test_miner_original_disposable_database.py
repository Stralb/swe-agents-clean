"""Run the byte-identical original Database only against disposable local DBs.

Never opens a cluster, Wits, or historical research database. Never invokes
live workers or scanner commands. Original mutating migrations are examined
only on a fresh TemporaryDirectory-created SQLite file.
"""
from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.db.database import Database

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "src/db/schema.sql"
FROZEN_SHA = "3412fedd504f1b78875fc2303a4e193a82d05bcfe567c3ecedea7cc697f77b90"
SNAPSHOTS = ("2026-08-17", "2026-08-19", "2026-10-20-live-export")


class OriginalDatabaseOnDisposableFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="arno_db_fixture_")
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "isolated" / "miner.sqlite"
        self.db = Database(self.db_path, read_only=False, command_spool=None)
        self.db.init_schema(SCHEMA)

    def test_exact_original_bytes_against_three_snapshots(self):
        active = (ROOT / "src/db/database.py").read_bytes()
        self.assertEqual(hashlib.sha256(active).hexdigest(), FROZEN_SHA)
        for date in SNAPSHOTS:
            with self.subTest(snapshot=date):
                self.assertEqual(active,
                    (ROOT / "historical/miner" / date / "src/db/database.py").read_bytes())

    def test_database_only_created_inside_temp_directory(self):
        self.assertTrue(self.db_path.is_file())
        self.assertEqual(self.db_path.parent, Path(self.tmp.name) / "isolated")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM tags")["n"], 12)
        self.assertEqual(self.db.one("PRAGMA foreign_keys")["foreign_keys"], 1)

    def test_init_schema_is_repeatable_on_fresh_fixture(self):
        self.db.init_schema(SCHEMA)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM tags")["n"], 12)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM repos")["n"], 0)

    def test_insert_or_get_repo_is_idempotent(self):
        repo = {"full_name": "example/repo", "html_url": "https://example.invalid/repo", "stargazers_count": 50}
        first = self.db.insert_or_get_repo(repo)
        again = self.db.insert_or_get_repo({**repo, "stargazers_count": 800})
        self.assertEqual(first, again)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM repos")["n"], 1)
        # Exact historical INSERT OR IGNORE leaves prior repo metadata intact.
        self.assertEqual(self.db.one("SELECT stars FROM repos")["stars"], 50)

    def _seed_case(self):
        repo = {"full_name": "example/repo", "html_url": "https://example.invalid/repo", "stargazers_count": 100}
        rid = self.db.insert_or_get_repo(repo)
        issue = {"id": 42, "number": 8, "html_url": "https://example.invalid/issues/8",
                 "title": "Fix issue", "body": "Reproduction: test fails", "user": {"login": "bob"},
                 "labels": [{"name": "bug"}], "comments": 1}
        pr = {"number": 12, "html_url": "https://example.invalid/pull/12",
              "title": "Fixes #8", "body": "Fixes #8", "user": {"login": "alice"},
              "head": {"ref": "codex/fix", "sha": "aa"},
              "base": {"ref": "main", "sha": "bb"}, "merged_at": "2026-10-01T10:00:00Z"}
        iid = self.db.upsert_issue(rid, issue, 3, True)
        pid = self.db.upsert_pr(rid, pr)
        self.db.link_issue_pr(iid, pid, "closing-keyword")
        cid = self.db.create_or_get_case(rid, iid, pid, "AI-explicit-high", ["AI-explicit-high"])
        return rid, iid, pid, cid

    def test_original_crud_issue_pr_case_and_foreign_keys(self):
        rid, iid, pid, cid = self._seed_case()
        self.assertGreater(cid, 0)
        item = self.db.one("SELECT * FROM cases WHERE id=?", (cid,))
        self.assertEqual(item["status"], "metadata_collected")
        self.assertEqual(item["ai_cohort"], "AI-explicit-high")
        self.assertEqual(self.db.one("SELECT method FROM issue_pr_links")["method"], "closing-keyword")
        self.assertEqual(self.db.one("SELECT word_count FROM issues")["word_count"], 3)
        self.assertEqual(self.db.one("SELECT head_ref FROM pull_requests")["head_ref"], "codex/fix")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM scanner_jobs")["n"], 0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO issues(repo_id,number,url) VALUES(?,?,?)", (9999, 1, "https://example.invalid/x"))

    def test_replace_pr_files_is_destructive_only_in_disposable_database(self):
        _, _, pid, _ = self._seed_case()
        self.db.replace_pr_files(pid, [{"filename": "src/app.ts", "patch": "+ fixed"}])
        self.db.replace_pr_files(pid, [{"filename": "src/another.ts"}])
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM pr_files")["n"], 1)
        self.assertEqual(self.db.one("SELECT filename FROM pr_files")["filename"], "src/another.ts")

    def test_replaying_case_upsert_does_not_duplicate_case(self):
        rid, iid, pid, cid = self._seed_case()
        cid2 = self.db.create_or_get_case(rid, iid, pid, "AI-unknown", ["AI-unknown"])
        self.assertEqual(cid, cid2)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM cases")["n"], 1)
        self.assertEqual(self.db.one("SELECT ai_cohort FROM cases")["ai_cohort"], "AI-unknown")

    def test_migration_backfills_scanner_jobs_and_changes_case_status(self):
        _, _, _, cid = self._seed_case()
        self.db.apply_migrations()
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM scanner_jobs WHERE case_id=?", (cid,))["n"], 5)
        self.assertEqual(self.db.one("SELECT status FROM cases WHERE id=?", (cid,))["status"], "scanner_running")
        self.db.apply_migrations()
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM scanner_jobs")["n"], 5)

    def test_migration_normalizes_skipped_and_drops_legacy_job_types(self):
        _, _, pid, cid = self._seed_case()
        self.db.execute("INSERT INTO scanner_jobs(case_id,job_type,status) VALUES(?,?,'skipped')", (cid, "source_code"))
        self.db.execute("INSERT INTO scanner_runs(case_id,pr_id,scanner,status) VALUES(?,?,?,'skipped')", (cid,pid,"codeql"))
        self.db.apply_migrations()
        self.assertIsNone(self.db.one("SELECT id FROM scanner_jobs WHERE job_type='source_code'"))
        self.assertEqual(self.db.one("SELECT status FROM scanner_runs")["status"], "not_applicable")

    def test_migration_resets_old_unaccounted_retrieval_only_in_temp_db(self):
        self.db.execute("INSERT INTO retrieval_queries(stream_key,term,final_query,raw_count,status) VALUES(?,?,?,?,?)",
                        ("test", "term", "is:pr test", 80, "ok"))
        self.db.apply_migrations()
        row = self.db.one("SELECT raw_count,next_page,status,last_error FROM retrieval_queries")
        self.assertEqual(row["raw_count"], 0)
        self.assertEqual(row["next_page"], 1)
        self.assertEqual(row["status"], "pending")
        self.assertIn("reset_legacy_unaccounted_retrieval_for_replay", row["last_error"])

    def test_read_only_can_query_but_not_write_without_spool(self):
        reader = Database(self.db_path, read_only=True, command_spool=None)
        self.assertEqual(reader.one("SELECT COUNT(*) AS n FROM repos")["n"], 0)
        with self.assertRaisesRegex(RuntimeError, "Read-only database"):
            reader.execute("DELETE FROM repos")
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM repos")["n"], 0)

    def test_original_module_import_does_not_construct_db_or_start_jobs(self):
        # Import does not open/create the DB, only explicit Database() does.
        with mock.patch("sqlite3.connect", side_effect=AssertionError("unexpected database connect")):
            import src.db.database as module
            self.assertTrue(callable(module.Database))


if __name__ == "__main__":
    unittest.main()
