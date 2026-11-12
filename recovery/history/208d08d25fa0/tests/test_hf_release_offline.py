import tempfile
import unittest
from pathlib import Path
from src.repro_store.store import EvidenceStore, EvidenceError
from src.repro_store.research import ResearchIndex
from src.repro_store.hf_release import local_release_manifest,publish_private

class HFReleasePreflight(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup)
        self.root=Path(t.name)/"safe"
        self.store=EvidenceStore.create(self.root)
        ResearchIndex(self.store)

    def test_deterministic_release_id(self):
        a=local_release_manifest(self.root)
        b=local_release_manifest(self.root)
        self.assertEqual(a["release_id"],b["release_id"])
        self.assertEqual(a["integrity_status"],"PASS")
        self.assertFalse(a["remote_publication_completed"])

    def test_default_preflight_requires_no_credentials(self):
        r=publish_private(self.root,repo_id="Stralb/malicious-issue-miner-data",execute=False,acknowledged=False,max_bytes=10000000)
        self.assertEqual(r["status"],"LOCAL_PREFLIGHT_ONLY")

    def test_remote_requires_acknowledgement(self):
        with self.assertRaises(EvidenceError):
            publish_private(self.root,repo_id="Stralb/malicious-issue-miner-data",execute=True,acknowledged=False,max_bytes=10000000)

    def test_wrong_repo_refused_before_network(self):
        with self.assertRaises(EvidenceError):
            publish_private(self.root,repo_id="someoneelse/dataset",execute=True,acknowledged=True,max_bytes=10000000)

    def test_symlink_rejected(self):
        (self.root/"link").symlink_to(self.root/"catalog.sqlite")
        with self.assertRaises(EvidenceError):
            local_release_manifest(self.root)

if __name__=="__main__":unittest.main()
