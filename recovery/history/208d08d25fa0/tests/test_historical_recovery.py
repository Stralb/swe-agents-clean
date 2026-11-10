"""Offline synthetic safety tests; no original experiments or cluster access."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.repro_store.store import EvidenceError,EvidenceStore
from src.repro_store.research import ResearchIndex
from src.repro_store.historical_recovery import HistoricalRecovery,PHASES,RECOVERY,_case
from src.repro_store.historical_cli import _connect,_archive_bytes,verify,status
from src.repro_store.portable_release import build_portable

class HistoricalSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.base=Path(self.tmp.name)
        self.src=self.base/'original.bin'
        self.src.write_bytes(b'ORIGINAL GENERATED PATCH\x00'*105)
        self.store=EvidenceStore.create(self.base/'vault',inline_limit=0)
        self.source_id,self.digest=self.store.ingest(
            self.src,origin_uri='test-origin:original-file',origin_revision='version-1',
            scientific_status='candidate')
        self.history=HistoricalRecovery(self.store)
    def tearDown(self):self.tmp.cleanup()

    def test_study_stages_have_distinct_keys(self):
        self.assertEqual(len(PHASES),16)
        self.assertEqual(len({a[0] for a in PHASES}),len(PHASES))
        self.assertEqual(set(RECOVERY),{a[0] for a in PHASES})

    def test_strict_case_ids(self):
        self.assertEqual(_case('00668'),'668')
        self.assertIsNone(_case('ERROR'))
        self.assertIsNone(_case(None))
        self.assertIsNone(_case(True))

    def test_original_vault_sha_verified(self):
        self.assertEqual(self.store.bytes_for_digest(self.digest),self.src.read_bytes())
        self.assertEqual(self.store.verify()['status'],'PASS')

    def test_portable_single_file_no_external_object_needed(self):
        dest=self.base/'portable.sqlite'
        output=build_portable(self.base/'vault',dest)
        self.assertEqual(output['embedded_external_objects'],1)
        with _connect(dest) as db:
            self.assertEqual(_archive_bytes(db,dest,self.digest),self.src.read_bytes())
            self.assertEqual(verify(db,dest)['status'],'PASS')
        self.assertTrue(dest.exists())

    def test_portable_create_only(self):
        dest=self.base/'portable.sqlite'
        build_portable(self.base/'vault',dest)
        with self.assertRaises(EvidenceError):build_portable(self.base/'vault',dest)

    def test_missing_unregistered_target_rejected(self):
        with self.assertRaises(EvidenceError):
            self.history.mark_recovered('fabricated-anon.zip',self.digest,evidence_location='test://')

    def test_claim_registry_seeded_not_promoted_to_validated(self):
        self.history._index_studies()
        self.history._index_claims()
        with self.store._open(readonly=True) as db:
            rows=db.execute('SELECT verification_status,COUNT(*) FROM historical_claim_register GROUP BY verification_status').fetchall()
        self.assertEqual(sum(n for _,n in rows),15)
        self.assertTrue(any(state=='disputed_historical_versions' for state,_ in rows))
        self.assertTrue(any(state=='reported_not_reproduced' for state,_ in rows))

    def test_immutable_historical_record(self):
        with self.store._open() as db:
            db.execute("INSERT INTO historical_study_register VALUES ('Q',1,'test','test','listed','test','test')")
        with self.assertRaises(sqlite3.DatabaseError):
            with self.store._open() as db:
                db.execute("UPDATE historical_study_register SET frozen_scope='new' WHERE study_id='Q'")

    def test_source_not_executable_from_import(self):
        dangerous=self.base/'historical_original.py'
        dangerous.write_text('raise RuntimeError("SHOULD NOT EXECUTE")\n')
        _,sha=self.store.ingest(dangerous,origin_uri='test://script',origin_revision='1')
        self.assertEqual(self.store.bytes_for_digest(sha),dangerous.read_bytes())

if __name__=='__main__': unittest.main()
