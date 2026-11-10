"""Synthetic ZIP integrity/SARIF tests; no private data, CodeQL or cluster needed."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.owp14_archive_audit import AuditError, read_json, sarif_count, verify_manifest


def build_zip(dst: Path, entries: dict[str, bytes], index_hash_override: dict[str, str] | None = None) -> None:
    index_hash_override = index_hash_override or {}
    rows = []
    for name, content in entries.items():
        rows.append({'archive_path': name, 'sha256':index_hash_override.get(name,hashlib.sha256(content).hexdigest()), 'bytes':len(content)})
    buf=io.StringIO()
    writer=csv.DictWriter(buf,fieldnames=['archive_path','sha256','bytes'])
    writer.writeheader()
    writer.writerows(rows)
    with zipfile.ZipFile(dst,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            z.writestr(name,content)
        z.writestr('00_README_AND_MANIFEST/PART_INDEX.csv',buf.getvalue())


class Owp14AuditSyntheticTests(unittest.TestCase):
    def test_complete_member_hash_manifest_passes(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'a.zip'
            build_zip(path,{'a/file.txt':b'data','a/result.json':b'{"runs":[]}'})
            with zipfile.ZipFile(path) as z:
                self.assertEqual(verify_manifest(z)['validated_member_hashes'],2)

    def test_member_sha_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'a.zip'
            build_zip(path,{'a/file.txt':b'altered'}, {'a/file.txt':'0'*64})
            with zipfile.ZipFile(path) as z, self.assertRaises(AuditError):
                verify_manifest(z)

    def test_missing_manifest_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'a.zip'
            build_zip(path,{'a/file.txt':b'data'})
            # Rewrite local test fixture only: the production auditor never writes archives.
            with zipfile.ZipFile(path,'a') as z:
                z.writestr('additional.bin',b'not indexed')
            with zipfile.ZipFile(path) as z, self.assertRaises(AuditError):
                verify_manifest(z)

    def test_sarif_result_count_and_locator(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'a.zip'
            body=json.dumps({'runs':[{'results':[{'ruleId':'js/redos','locations':[{'physicalLocation':{
                'artifactLocation':{'uri':'src/main.js'},'region':{'startLine':17}
            }}]}]}]}).encode()
            build_zip(path,{'root/CASE_00001/after.sarif':body})
            with zipfile.ZipFile(path) as z:
                self.assertEqual(sarif_count(z,'CASE_00001/after.sarif'),(1,{('js/redos','src/main.js',17)}))
                self.assertEqual(len(read_json(z,'CASE_00001/after.sarif')['runs']),1)

    def test_ambiguous_member_suffix_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path=Path(work)/'a.zip'
            build_zip(path,{'a/RESULT.json':b'{}','b/RESULT.json':b'{}'})
            with zipfile.ZipFile(path) as z, self.assertRaises(AuditError):
                read_json(z,'RESULT.json')


if __name__=='__main__':
    unittest.main()
