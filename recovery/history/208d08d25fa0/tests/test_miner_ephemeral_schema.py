"""In-memory-only tests of the exact archived miner schema.sql."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import unittest
from unittest import mock

from src.db.ephemeral import SCHEMA_SHA256, SchemaMismatchError, open_ephemeral_database, verified_schema_sql

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ('2026-08-17','2026-08-19','2026-10-20-live-export')


class EphemeralSchemaTests(unittest.TestCase):
    def test_bundled_schema_hash_and_historical_equality(self):
        blob = (ROOT / 'src/db/schema.sql').read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), SCHEMA_SHA256)
        for stamp in HISTORICAL:
            with self.subTest(stamp=stamp):
                self.assertEqual((ROOT / 'historical/miner' / stamp / 'src/db/schema.sql').read_bytes(), blob)
        self.assertIn('CREATE TABLE IF NOT EXISTS issues', verified_schema_sql())

    def test_memory_only_database_list(self):
        con = open_ephemeral_database()
        try:
            self.assertEqual([tuple(x) for x in con.execute('PRAGMA database_list')], [(0, 'main', '')])
            self.assertEqual(con.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        finally:
            con.close()

    def test_exact_base_table_and_explicit_index_count(self):
        con = open_ephemeral_database()
        try:
            tables = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            self.assertEqual(len(tables), 24)
            self.assertTrue({'repos','issues','pull_requests','issue_pr_links','cases','scanner_jobs','github_rate_limits','daemon_controls'}.issubset(tables))
            indexes = [x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")]
            self.assertEqual(len(indexes), 13)
        finally:
            con.close()

    def test_synthetic_repo_issue_pr_link_case_insert(self):
        con = open_ephemeral_database()
        try:
            repo_id = con.execute("INSERT INTO repos(full_name, html_url) VALUES(?, ?)", ('example/project', 'https://example.invalid/project')).lastrowid
            issue_id = con.execute("INSERT INTO issues(repo_id, number, url, title) VALUES(?, ?, ?, ?)", (repo_id, 8, 'https://example.invalid/issues/8', 'Build failure')).lastrowid
            pr_id = con.execute("INSERT INTO pull_requests(repo_id, number, url, title) VALUES(?, ?, ?, ?)", (repo_id, 12, 'https://example.invalid/pulls/12', 'Fixes #8')).lastrowid
            con.execute("INSERT INTO issue_pr_links(issue_id,pr_id,method) VALUES(?, ?, ?)", (issue_id,pr_id,'closing-keyword'))
            con.execute("INSERT INTO cases(repo_id,issue_id,pr_id) VALUES(?,?,?)", (repo_id,issue_id,pr_id))
            row = con.execute('SELECT i.number AS issue_number, p.number AS pr_number FROM cases c JOIN issues i ON i.id=c.issue_id JOIN pull_requests p ON p.id=c.pr_id').fetchone()
            self.assertEqual(dict(row), {'issue_number':8,'pr_number':12})
        finally:
            con.close()

    def test_foreign_key_constraints_active(self):
        con = open_ephemeral_database()
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('INSERT INTO issues(repo_id, number, url) VALUES(?, ?, ?)', (999, 1, 'https://example.invalid'))
        finally:
            con.close()

    def test_duplicate_repo_names_rejected(self):
        con = open_ephemeral_database()
        try:
            con.execute('INSERT INTO repos(full_name, html_url) VALUES(?, ?)', ('r/x','https://example.invalid/1'))
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute('INSERT INTO repos(full_name, html_url) VALUES(?, ?)', ('r/x','https://example.invalid/2'))
        finally:
            con.close()

    def test_schema_corruption_refused_before_sqlite_connect(self):
        with mock.patch('src.db.ephemeral.resources.files') as files:
            files.return_value.joinpath.return_value.read_bytes.return_value = b'DROP TABLE repos;'
            with mock.patch('src.db.ephemeral.sqlite3.connect', side_effect=AssertionError('should not connect')):
                with self.assertRaises(SchemaMismatchError):
                    open_ephemeral_database()

    def test_uses_memory_only_connection_path(self):
        original = sqlite3.connect
        with mock.patch('src.db.ephemeral.sqlite3.connect', wraps=original) as spy:
            con = open_ephemeral_database()
            spy.assert_called_once_with(':memory:')
            con.close()
