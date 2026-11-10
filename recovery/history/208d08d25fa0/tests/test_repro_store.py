"""Synthetic tests only; never contact the cluster or Hugging Face."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.repro_store import EvidenceError, EvidenceStore
from src.repro_store.cli import main


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "fresh-vault"
        self.store = EvidenceStore.create(self.root, inline_limit=8)
        self.original = self.base / "patch.diff"
        self.original.write_bytes(b"+++ a/file\n+safe\n")

    def ingest(self):
        return self.store.ingest(self.original, origin_uri="wits://example/patch.diff",
                                  origin_revision="commit:abc123")

    def test_new_only_creation(self):
        with self.assertRaises(EvidenceError):
            EvidenceStore.create(self.root)

    def test_content_address_copy_and_original_preservation(self):
        original = self.original.read_bytes()
        sid, digest = self.ingest()
        self.assertEqual(digest, hashlib.sha256(original).hexdigest())
        self.assertEqual(self.store.bytes_for_digest(digest), original)
        self.assertEqual(self.original.read_bytes(), original)
        self.assertEqual(self.store.verify()["status"], "PASS")
        self.assertEqual(self.store.verify()["artifacts"], 1)
        self.assertEqual(self.store.verify()["sources"], 1)
        self.assertTrue((self.root / "objects" / digest[:2] / digest[2:]).is_file())

    def test_two_sources_one_blob(self):
        a, digest = self.ingest()
        b, digest2 = self.ingest()
        self.assertNotEqual(a, b)
        self.assertEqual(digest, digest2)
        self.assertEqual(self.store.verify()["artifacts"], 1)
        self.assertEqual(self.store.verify()["sources"], 2)

    def test_link_and_lookup(self):
        sid, sha = self.ingest()
        self.store.link(sid, unit_type="root", unit_id="CROOT-1234-01", evidence_role="diff",
                        analysis_stage="C", blinding="blind", method_revision="codebook-v1")
        found = self.store.find("root", "CROOT-1234-01")
        self.assertEqual(found[0]["sha256"], sha)
        self.assertEqual(found[0]["blinding"], "blind")
        self.assertEqual(len(self.store.find("root", "CROOT-NOT-FOUND")), 0)

    def test_derive_and_manifest(self):
        _, parent = self.ingest()
        other = self.base / "scanner.sarif"
        other.write_text('{"runs": []}')
        _, child = self.store.ingest(other, origin_uri="wits://sample", origin_revision="2026-10-23")
        self.store.derive(parent, child, relationship="scanned_to", code_revision="scanner:v1")
        manifest = self.store.manifest()
        self.assertEqual(len(manifest["derivations"]), 1)
        self.assertEqual(manifest["derivations"][0]["parent_sha256"], parent)

    def test_inline_storage_and_integrity(self):
        self.original.write_bytes(b"tiny")
        _, sha = self.ingest()
        self.assertEqual(self.store.bytes_for_digest(sha), b"tiny")
        self.assertEqual(self.store.verify()["status"], "PASS")

    def test_bad_hash_and_source_mutation_not_ingested(self):
        with self.assertRaises(EvidenceError):
            self.store.ingest(self.original, origin_uri="uri", origin_revision="rev", expected_sha256="0" * 64)
        self.assertEqual(self.store.verify()["artifacts"], 0)

    def test_tampered_cas_detected(self):
        _, sha = self.ingest()
        (self.root / "objects" / sha[:2] / sha[2:]).write_bytes(b"tampered")
        result = self.store.verify()
        self.assertEqual(result["status"], "FAIL")
        with self.assertRaises(EvidenceError):
            self.store.bytes_for_digest(sha)

    def test_symlink_rejected(self):
        other = self.base / "link.diff"
        other.symlink_to(self.original)
        with self.assertRaises(EvidenceError):
            self.store.ingest(other, origin_uri="uri", origin_revision="rev")

    def test_raw_catalog_is_not_old_miner_schema(self):
        with closing(sqlite3.connect(self.root / "catalog.sqlite")) as cx:
            names = {x[0] for x in cx.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("artifacts", names)
        self.assertNotIn("scanner_jobs", names)
        self.assertNotIn("cases", names)

    def test_invalid_sensitivity_rejected_before_blob_copy(self):
        with self.assertRaises(EvidenceError):
            self.store.ingest(self.original, origin_uri="uri", origin_revision="rev", sensitivity="public")
        self.assertEqual(self.store.verify()["artifacts"], 0)

    def test_append_only_rows(self):
        source_id, digest = self.ingest()
        with closing(sqlite3.connect(self.root / "catalog.sqlite")) as cx:
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("UPDATE sources SET scientific_status='verified' WHERE source_id=?", (source_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("DELETE FROM artifacts WHERE sha256=?", (digest,))

    def test_cli_verify(self):
        self.ingest()
        self.assertEqual(main(["verify", str(self.root)]), 0)


if __name__ == "__main__":
    unittest.main()
