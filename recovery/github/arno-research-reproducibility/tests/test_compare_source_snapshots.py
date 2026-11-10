import hashlib
import io
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.compare_source_snapshots import compare, canonical_path

class SnapshotTests(unittest.TestCase):
    def test_canonical_path_rejects_backups_and_unrelated(self):
        self.assertEqual(canonical_path('malicious-issue-miner-rate-smart/src/scanners/a.py'),'src/scanners/a.py')
        self.assertIsNone(canonical_path('malicious-issue-miner-rate-smart/backups/a.py'))
        self.assertIsNone(canonical_path('malicious-issue-miner-rate-smart/src/a.py.before-old'))

    def test_diff_classifies_versions(self):
        with tempfile.TemporaryDirectory() as dirname:
            home=Path(dirname); old=home/'old.zip'; new=home/'new.zip'; live=home/'live.tar.gz'
            with zipfile.ZipFile(old,'w') as z:
                z.writestr('malicious-issue-miner-rate-smart-main/src/common.py','x = 1\n')
                z.writestr('malicious-issue-miner-rate-smart-main/src/update.py','x = 1\n')
            with zipfile.ZipFile(new,'w') as z:
                z.writestr('malicious-issue-miner-rate-smart-main/src/common.py','x = 1\n')
                z.writestr('malicious-issue-miner-rate-smart-main/src/update.py','x = 1\n')
                z.writestr('malicious-issue-miner-rate-smart-main/ui/extra.py','x = 2\n')
            with tarfile.open(live,'w:gz') as z:
                for path,txt in [('src/common.py','x = 1\n'),('src/update.py','x = 3\n')]:
                    b=txt.encode();info=tarfile.TarInfo('malicious-issue-miner-rate-smart/'+path);info.size=len(b);z.addfile(info,io.BytesIO(b))
            status,rows=compare(old,new,live)
            d={r['source_path']:r['classification'] for r in rows}
            self.assertEqual(d['src/common.py'],'IDENTICAL_ALL_THREE')
            self.assertEqual(d['src/update.py'],'LIVE_DIFFERS_FROM_AUG17')
            self.assertEqual(d['ui/extra.py'],'ONLY_AUG19')

if __name__ == '__main__':unittest.main()
