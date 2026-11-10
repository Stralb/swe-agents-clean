"""Source CSVs can be reviewed even before patch bytes are recovered."""
from __future__ import annotations
import hashlib,json,tempfile,unittest
from pathlib import Path
from src.repro_store import EvidenceStore,EvidenceError
from src.repro_store.source_runs import index_blinded_run_metadata,STUDY_ID
from src.repro_store.reviewer import ReviewerView

class SourceRunsTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.store=EvidenceStore.create(self.root/'vault')
        self.manifest=self.root/'BLINDED_MANIFEST.csv'
        self.summary=self.root/'BLINDED_CODEQL_SUMMARY.csv'
        self.qc=self.root/'STEP4_QC.json'
        self.manifest.write_text('run_id,patch_sha256,report_sha256\nG001,abc,def\nG002,qwe,rty\n')
        self.summary.write_text('run_id,patch_apply,target_present\nG001,PASS,NO\nG002,PASS,NO\n')
        self.qc.write_text(json.dumps({'runs_expected':2,'runs_summarized':2}))

    def test_stored_observations_are_not_generated_patches(self):
        x=index_blinded_run_metadata(self.store,self.manifest,self.summary,self.qc)
        self.assertEqual(x['run_count'],2)
        v=ReviewerView(self.store)
        r=v.run_dossier(STUDY_ID,'G001')
        self.assertEqual(r['status'],'SOURCE_OBSERVATIONS_ONLY_NOT_A_GENERATED_PATCH_IMPORT')
        self.assertEqual(len(r['raw_source_observations']),2)
        self.assertIsNone(r['arm'])
        self.assertEqual(v.study_coverage(STUDY_ID)['source_observed_run_ids'],2)
        self.assertEqual(v.study_coverage(STUDY_ID)['runs'],0)
        rep=index_blinded_run_metadata(self.store,self.manifest,self.summary,self.qc)
        self.assertEqual(rep['batches']['scanner_summary']['status'],'ALREADY_INDEXED')

    def test_mismatched_runs_fail_closed(self):
        self.summary.write_text('run_id,patch_apply\nG001,PASS\n')
        with self.assertRaisesRegex(EvidenceError,'Run IDs/counts mismatch'):
            index_blinded_run_metadata(self.store,self.manifest,self.summary,self.qc)

if __name__=='__main__':unittest.main()
