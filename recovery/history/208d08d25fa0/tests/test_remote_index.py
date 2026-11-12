"""Synthetic coverage and evidence-bounded assertions; no network access."""
from __future__ import annotations
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from src.repro_store import EvidenceStore, EvidenceError
from src.repro_store.remote_index import RemoteEvidenceLedger


class RemoteIndexTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=EvidenceStore.create(self.root/"store")
        self.ledger=RemoteEvidenceLedger(self.store)
        self.blob=b"original source patch bytes"
        self.expected_sha=hashlib.sha256(self.blob).hexdigest()
        self.file=self.root/"manifest.json"
        self.manifest={"format":"arno-readonly-source-expectations-v1",
                       "study_id":"S5PAIR001_STEP4_BLINDED","observed_date":"2026-10-25",
                       "observations":[
                           {"run_id":"G001","role":"generated_patch",
                            "remote_uri":"wits://research_artifacts/step4/input/patches/G001.patch",
                            "expected_sha256":self.expected_sha,"expected_bytes":len(self.blob),
                            "hash_authority":"frozen-original-source-manifest",
                            "identity_basis":"exact-original-run-manifest-row",
                            "blinding":"blind","observation_status":"remote_source_reported"},
                           {"run_id":"G001","role":"scanner_after",
                            "remote_uri":"wits://research_artifacts/step4/results/runs/G001/results.sarif",
                            "expected_sha256":None,"expected_bytes":1234,
                            "hash_authority":"no-full-file-hash-seen",
                            "identity_basis":"connector-file-list",
                            "blinding":"blind","observation_status":"connector_listed"}]}
        self.file.write_text(json.dumps(self.manifest))

    def register(self):
        return self.ledger.register(self.file,origin_uri="researcher-intake://observations",origin_revision="observation:2026-10-25")

    def test_missing_until_exact_original_bytes_available(self):
        r=self.register()
        self.assertEqual(r["expectations"],2)
        coverage=self.ledger.coverage("S5PAIR001_STEP4_BLINDED")
        self.assertEqual(coverage["states"]["EXPECTED_HASH_NOT_LOCALLY_CAPTURED"],1)
        self.assertEqual(coverage["states"]["NO_SOURCE_HASH_AND_NOT_LOCALLY_CAPTURED"],1)
        src=self.root/"original.patch"
        src.write_bytes(self.blob)
        self.store.ingest(src,origin_uri="wits://step4/input/patches/G001.patch",origin_revision="source_sha:"+self.expected_sha)
        coverage=self.ledger.coverage("S5PAIR001_STEP4_BLINDED")
        self.assertEqual(coverage["states"]["PRESENT_WITH_VERIFIED_BYTES"],1)
        self.assertEqual(coverage["states"]["NO_SOURCE_HASH_AND_NOT_LOCALLY_CAPTURED"],1)

    def test_tamper_detection_returns_corrupt(self):
        self.register()
        src=self.root/"original.patch"
        src.write_bytes(self.blob)
        self.store.ingest(src,origin_uri="u",origin_revision="r")
        with self.store._open() as cx:
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("UPDATE expected_evidence SET evidence_role='new' WHERE expected_id=1")
        with sqlite3.connect(self.store.db_path) as cx:
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("DELETE FROM expected_evidence")
        with sqlite3.connect(self.store.db_path) as cx:
            with self.assertRaises(sqlite3.IntegrityError):
                cx.execute("UPDATE artifacts SET inline_bytes=? WHERE sha256=?",(b"corrupt",self.expected_sha))

    def test_repeated_manifest_idempotent(self):
        first=self.register()
        again=self.register()
        self.assertEqual(again["status"],"ALREADY_REGISTERED_UNCHANGED")
        self.assertEqual(again["expectations"],first["expectations"])

    def test_duplicate_observation_rejected(self):
        self.manifest["observations"].append(self.manifest["observations"][0])
        self.file.write_text(json.dumps(self.manifest))
        with self.assertRaisesRegex(EvidenceError,"Duplicate locator"):
            self.register()

    def test_corrupt_local_hash_assertion_rejected(self):
        self.manifest["observations"][0]["expected_sha256"]="abc"
        self.file.write_text(json.dumps(self.manifest))
        with self.assertRaises(EvidenceError):
            self.register()

    def test_false_locally_hash_checked_assertion_rejected(self):
        self.manifest["observations"][1]["observation_status"]="locally_hash_checked"
        self.file.write_text(json.dumps(self.manifest))
        with self.assertRaises(EvidenceError):
            self.register()

if __name__=="__main__":unittest.main()
