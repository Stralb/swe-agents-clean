"""Tests of source-derived SQLite fingerprint and exact historical case SELECT."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from analysis.discovery_database_source_lineage import (
    CASE_QUERY, DECLARED_CASES, DECLARED_DISCOVERY_SHA256,
    DiscoveryLineageError, ROOT, archived_discovery_fingerprint,
    main, replay_exact_case_query, verify_source_locked_discovery_snapshot,
)
from tests.test_frozen_sqlite_intake import manifest_for, synthetic_db


class DiscoveryDatabaseSourceLineageTests(unittest.TestCase):
    def test_three_source_embedded_sha_and_one_exact_original_cases_query(self):
        result = archived_discovery_fingerprint()
        self.assertEqual(result["status"],
                         "ARCHIVED_ANALYSIS_FINGERPRINT_SOURCE_VERIFIED")
        self.assertEqual(result["source_declared_case_rows"], 3809)
        self.assertEqual(
            result["source_declared_discovery_database_sha256"],
            DECLARED_DISCOVERY_SHA256,
        )
        self.assertEqual(
            result["source_declared_case_linkage_sql_sha256"],
            hashlib.sha256(CASE_QUERY.encode()).hexdigest(),
        )
        self.assertEqual(result["pinned_source_files_verified"], 5)
        self.assertEqual(result["independent_embedded_database_hash_definitions"], 3)
        self.assertFalse(result["actual_source_sqlite_snapshot_present"])
        self.assertFalse(result["original_3809_case_linkage_rows_reexecuted"])
        self.assertFalse(result["192_positive_workflows_reproduced"])

    def test_exact_sql_names_logical_case_linkage_not_scanner_findings(self):
        self.assertEqual(
            CASE_QUERY,
            "SELECT id AS case_id, repo_id, issue_id, pr_id FROM cases ORDER BY id",
        )
        self.assertEqual(DECLARED_CASES, 3809)
        self.assertNotIn("scanner", CASE_QUERY)
        self.assertNotIn("JOIN", CASE_QUERY)

    def test_missing_archival_files_refuses_false_source_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DiscoveryLineageError):
                archived_discovery_fingerprint(Path(tmp))

    def test_modified_archival_file_is_rejected_without_import_or_execution(self):
        relative = (
            "historical/miner/2026-10-20-live-export/"
            "analysis/full_corpus_discovery_v1_1/discovery.py"
        )
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / relative
            dest.parent.mkdir(parents=True)
            orig = ROOT / relative
            dest.write_bytes(orig.read_bytes() + b"\n# deliberately altered\n")
            with self.assertRaisesRegex(DiscoveryLineageError, "SHA mismatch"):
                archived_discovery_fingerprint(Path(tmp))

    @staticmethod
    def _conn(rows):
        con = sqlite3.connect(":memory:")
        con.execute(
            "CREATE TABLE cases("
            "id INTEGER, repo_id INTEGER, issue_id INTEGER, pr_id INTEGER)"
        )
        con.executemany("INSERT INTO cases VALUES(?,?,?,?)", rows)
        con.execute("PRAGMA query_only=ON")
        return con

    def test_synthetic_two_case_linkage_query(self):
        conn = self._conn([(5, 8, 11, 15), (6, 8, 12, 16)])
        try:
            result = replay_exact_case_query(conn, expected=2)
            self.assertEqual(result["case_rows"], 2)
            self.assertEqual(result["unique_case_ids"], 2)
            self.assertEqual(result["exact_source_case_linkage_sql"],
                             "REEXECUTED_READ_ONLY")
            self.assertEqual(conn.execute("PRAGMA query_only").fetchone()[0], 1)
        finally:
            conn.close()

    def test_duplicate_case_ids_block_replay(self):
        conn = self._conn([(5, 8, 11, 15), (5, 8, 12, 16)])
        try:
            with self.assertRaisesRegex(DiscoveryLineageError, "duplicate"):
                replay_exact_case_query(conn, expected=2)
        finally:
            conn.close()

    def test_null_case_linkage_blocks_replay(self):
        conn = self._conn([(5, 8, 11, 15), (6, 8, None, 16)])
        try:
            with self.assertRaisesRegex(DiscoveryLineageError, "null"):
                replay_exact_case_query(conn, expected=2)
        finally:
            conn.close()

    def test_wrong_case_denominator_is_not_silently_accepted(self):
        conn = self._conn([(5, 8, 11, 15), (6, 8, 12, 16)])
        try:
            with self.assertRaisesRegex(DiscoveryLineageError, "expected 3809"):
                replay_exact_case_query(conn)
        finally:
            conn.close()

    def test_changed_sql_is_refused_even_when_it_yields_same_number(self):
        conn = self._conn([(5, 8, 11, 15)])
        try:
            with self.assertRaisesRegex(DiscoveryLineageError, "Unapproved"):
                replay_exact_case_query(
                    conn, query="SELECT id FROM cases ORDER BY id",
                    expected=1,
                )
        finally:
            conn.close()

    def test_synthetic_db_cannot_be_claimed_as_original_discovery_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db = synthetic_db(directory)
            manifest = manifest_for(directory, db)
            with self.assertRaisesRegex(DiscoveryLineageError, "differs from the SHA"):
                verify_source_locked_discovery_snapshot(db, manifest)

    def test_status_command_explicitly_blocks_missing_sqlite(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            exit_code = main(["audit-source"])
        self.assertEqual(exit_code, 0)
        self.assertFalse(
            json.loads(out.getvalue())["original_3809_case_linkage_rows_reexecuted"]
        )

    def test_snapshot_cli_returns_blocking_exit_without_original_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            db = synthetic_db(directory)
            manifest = manifest_for(directory, db)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                exit_code = main([
                    "verify-discovery-snapshot", str(db), str(manifest),
                ])
        self.assertEqual(exit_code, 2)
        self.assertEqual(
            json.loads(out.getvalue())["status"],
            "BLOCKED_DISCOVERY_SOURCE_OR_DATA",
        )


if __name__ == "__main__":
    unittest.main()
