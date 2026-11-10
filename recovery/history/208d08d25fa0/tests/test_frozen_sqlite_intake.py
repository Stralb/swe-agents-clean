"""Synthetic-only, fail-closed tests for frozen miner SQLite intake.

All SQL creates *new disposable* tiny fixture files. No Wits DB is used,
and the historical Database class (which migrates/writes) is never invoked.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from analysis.frozen_sqlite_intake import (
    CANDIDATE_ROLE, IDENTITY, SnapshotIntakeError, main,
    verify_candidate,
)
from src.db.ephemeral import verified_schema_sql


def synthetic_db(directory: Path) -> Path:
    filename = directory / "fake-historical-miner.sqlite"
    with sqlite3.connect(filename) as conn:
        conn.executescript(verified_schema_sql())
        conn.execute(
            "INSERT INTO repos (full_name, html_url) VALUES (?, ?)",
            ("fixture/synthetic-repo", "https://example.invalid/synthetic"),
        )
        conn.commit()
    return filename


def manifest_for(directory: Path, path: Path, **changes) -> Path:
    manifest = {
        "schema_version": 1,
        "artifact_role": CANDIDATE_ROLE,
        "source_identity": IDENTITY,
        "capture_method": "sqlite_backup_api",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }
    manifest.update(changes)
    location = directory / "private-candidate-manifest.json"
    location.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    return location


class FrozenSQLiteCandidateIntakeTests(unittest.TestCase):
    def test_exact_sha_and_schema_verified_but_scientific_reproduction_false(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db)
            before = db.read_bytes()
            report = verify_candidate(db, manifest)
            self.assertEqual(report["status"], "PASS_CANDIDATE_SQLITE_INTEGRITY_ONLY")
            self.assertEqual(report["sqlite_integrity_check"], "ok")
            self.assertEqual(report["minimal_archived_miner_schema"], "compatible")
            self.assertEqual(
                report["known_table_counts_unfiltered"]["repos"], 1,
            )
            self.assertEqual(
                report["known_table_counts_unfiltered"]["cases"], 0,
            )
            self.assertEqual(len(report["sqlite_schema_sha256"]), 64)
            self.assertEqual(report["candidate_sha256"], hashlib.sha256(before).hexdigest())
            self.assertEqual(report["journal_header_mode"], "rollback_header")
            self.assertFalse(report["original_source_identity_independently_verified"])
            self.assertFalse(report["historical_cohort_inclusion_sql_verified"])
            self.assertFalse(report["reported_3809_workflows_reproduced"])
            self.assertFalse(report["reported_192_positive_workflows_reproduced"])
            self.assertFalse(report["reported_455_producing_changes_reproduced"])
            self.assertFalse(report["statistical_results_reproduced"])
            self.assertIn("NOT cohort", report["warning"])
            self.assertEqual(db.read_bytes(), before)
            self.assertFalse(Path(str(db) + "-wal").exists())
            self.assertFalse(Path(str(db) + "-shm").exists())

    def test_fake_candidate_hash_is_rejected_even_if_sqlite_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db, sha256="0" * 64)
            with self.assertRaisesRegex(SnapshotIntakeError, "SHA-256 differs"):
                verify_candidate(db, manifest)

    def test_wrong_byte_count_rejected_before_opening(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db, bytes=db.stat().st_size + 1)
            with self.assertRaisesRegex(SnapshotIntakeError, "byte length"):
                verify_candidate(db, manifest)

    def test_manifest_cannot_promote_provenance_to_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(
                root, db, source_identity="ORIGINAL_VERIFIED_WITHOUT_SOURCE",
            )
            with self.assertRaisesRegex(SnapshotIntakeError, "unproved original"):
                verify_candidate(db, manifest)

    def test_snapshot_capture_method_requires_explicit_declaration(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db, capture_method="unspecified")
            with self.assertRaisesRegex(SnapshotIntakeError, "capture method"):
                verify_candidate(db, manifest)

    def test_sqlite_candidate_path_cannot_be_a_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db)
            alias = root / "fake-alias.sqlite"
            alias.symlink_to(db)
            with self.assertRaisesRegex(SnapshotIntakeError, "symlink"):
                verify_candidate(alias, manifest)

    def test_non_sqlite_text_file_rejected_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "fake-historical.sqlite"
            path.write_bytes(b"NOT_SQLITE" + b"x" * 1024)
            manifest = manifest_for(root, path)
            with self.assertRaisesRegex(SnapshotIntakeError, "not an SQLite"):
                verify_candidate(path, manifest)

    def test_missing_required_miner_tables_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "wrong.sqlite"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE arbitrary (id INTEGER)")
            manifest = manifest_for(root, path)
            with self.assertRaisesRegex(SnapshotIntakeError, "Missing required"):
                verify_candidate(path, manifest)

    def test_wal_sidecars_refused_before_any_immutable_read(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            writer = sqlite3.connect(db)
            try:
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute(
                    "INSERT INTO repos(full_name,html_url) VALUES(?,?)",
                    ("fixture/second", "https://example.invalid/second"),
                )
                writer.commit()
                self.assertTrue(Path(str(db) + "-wal").exists())
                manifest = manifest_for(root, db)
                with self.assertRaisesRegex(SnapshotIntakeError, "sidecar -wal"):
                    verify_candidate(db, manifest)
            finally:
                writer.close()

    def test_stale_journal_sidecar_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db)
            Path(str(db) + "-journal").write_bytes(b"")
            with self.assertRaisesRegex(SnapshotIntakeError, "sidecar -journal"):
                verify_candidate(db, manifest)

    def test_manifest_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db)
            alias = root / "manifest-symlink.json"
            alias.symlink_to(manifest)
            with self.assertRaisesRegex(SnapshotIntakeError, "symlink"):
                verify_candidate(db, alias)

    def test_inspection_does_not_fix_or_migrate_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            with sqlite3.connect(db) as conn:
                conn.execute("DROP TABLE cases")
            manifest = manifest_for(root, db)
            before = db.read_bytes()
            with self.assertRaisesRegex(SnapshotIntakeError, "Missing required"):
                verify_candidate(db, manifest)
            self.assertEqual(db.read_bytes(), before)
            with sqlite3.connect(db) as conn:
                self.assertFalse(conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cases'"
                ).fetchone())

    def test_verified_self_declared_candidate_manifest_rejected_on_unknown_version(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db, schema_version=2)
            with self.assertRaisesRegex(SnapshotIntakeError, "manifest version"):
                verify_candidate(db, manifest)

    def test_empty_private_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = root / "private.json"
            manifest.write_text("{}")
            with self.assertRaisesRegex(SnapshotIntakeError, "manifest version"):
                verify_candidate(db, manifest)

    def test_committed_frozen_db_status_remains_explicitly_blocked(self):
        from analysis.frozen_sqlite_intake import ROOT
        path = ROOT / "provenance" / "frozen_database_recovery_status.json"
        status = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            status["status"],
            "LOCATED_CLUSTER_AND_HF_REFERENCE_BYTES_NOT_HASH_VERIFIED",
        )
        self.assertIsNone(status["source_database_sha256"])
        self.assertIsNone(status["source_database_bytes"])
        self.assertIsNone(status["frozen_historical_cohort_sql_sha256"])
        self.assertEqual(
            status["source_declared_discovery_database_sha256"],
            "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa",
        )
        self.assertEqual(status["source_declared_discovery_case_linkage_count"], 3809)
        self.assertTrue(status["exact_archived_discovery_case_sql_recovered"])
        self.assertFalse(status["source_expected_discovery_hash_matched_to_actual_db_bytes"])
        self.assertFalse(status["original_raw_database_in_repository"])
        self.assertFalse(status["huggingface_private_repo_access_verified"])
        self.assertFalse(status["source_capture_provenance_verified"])
        self.assertEqual(status["readonly_cluster_observations"]["cluster_sql_case_count_continuation"], 3809)
        self.assertEqual(status["readonly_cluster_observations"]["cluster_sql_case_count_aug17_hf_snapshot"], 3809)
        self.assertEqual(status["independently_reproduced_observations"], [])
        self.assertEqual(status["source_reported_observations"], {
            "workflows": 3809,
            "scanner_positive_workflows": 192,
            "precisely_mapped_positive_workflows": 191,
            "mapped_producing_changes": 455,
            "c_roots": 342,
        })

    def test_cli_exit_codes_indicate_candidate_not_historical_parity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = synthetic_db(root)
            manifest = manifest_for(root, db)
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                ok = main(["verify-candidate", str(db), str(manifest)])
            self.assertEqual(ok, 0)
            report = json.loads(stdout.getvalue())
            self.assertFalse(report["reported_3809_workflows_reproduced"])
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                bad = main([
                    "verify-candidate",
                    str(root / "unavailable-original.sqlite"), str(manifest),
                ])
            self.assertEqual(bad, 2)
            blocked = json.loads(stdout.getvalue())
            self.assertEqual(blocked["status"], "BLOCKED_SQLITE_CANDIDATE_NOT_VERIFIED")
            self.assertFalse(blocked["historical_counts_reproduced"])


if __name__ == "__main__":
    unittest.main()
