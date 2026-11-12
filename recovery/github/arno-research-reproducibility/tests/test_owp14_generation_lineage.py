"""Synthetic zip and lineage tests; do not use historical private source."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.owp14_generation_lineage import (
    LineageError,entry,indexed_archive,screening_groups,hash_file,compare_inner_transfer
)


def fixture_members():
    return {
      '02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/example/a.patch':b'one\n',
      '02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/example/b.patch':b'two\n',
    }


def fixture_zip(path,files,*,corrupt_hash=False,omit_row=False):
    out=io.StringIO()
    writer=csv.DictWriter(out,fieldnames=['archive_path','sha256','bytes'])
    writer.writeheader()
    rows=list(files.items())
    if omit_row:rows=rows[:-1]
    for idx,(name,body) in enumerate(rows):
        sha=hashlib.sha256(body).hexdigest()
        if corrupt_hash and idx==0:sha='0'*64
        writer.writerow({'archive_path':name,'sha256':sha,'bytes':len(body)})
    with zipfile.ZipFile(path,'w') as z:
        for name,body in files.items():z.writestr(name,body)
        z.writestr('00_README_AND_MANIFEST/PART_INDEX.csv',out.getvalue())


class LineageTests(unittest.TestCase):
    def test_complete_hash_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.zip';fixture_zip(p,fixture_members())
            with zipfile.ZipFile(p) as z:
                self.assertEqual(indexed_archive(z),2)
            self.assertEqual(len(hash_file(p)),64)

    def test_corrupt_hash_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.zip';fixture_zip(p,fixture_members(),corrupt_hash=True)
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(LineageError):indexed_archive(z)

    def test_missing_index_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.zip';fixture_zip(p,fixture_members(),omit_row=True)
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(LineageError):indexed_archive(z)

    def test_member_lookup_requires_unique_suffix(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('a/x/RESULT.json','{}');z.writestr('b/x/RESULT.json','{}')
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(LineageError):entry(z,'x/RESULT.json')

    def test_screening_membership_missing_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/screen65_A/CASE_00001.patch','sample')
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(LineageError):screening_groups(z)


    def test_screening_three_rounds_65_distinct_patches(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'stages.zip'
            with zipfile.ZipFile(p,'w') as z:
                for stage in ('screen65_first','screen65_second','screen65_third'):
                    for case in range(65):
                        z.writestr(f'02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/{stage}/CASE_{case:05d}.patch', f'{stage} {case}')
            with zipfile.ZipFile(p) as z:
                result=screening_groups(z)
            self.assertEqual(result['distinct_cases'],65)
            self.assertEqual(result['patches_across_three_stages'],195)
            self.assertEqual(result['cases_with_identical_patch_bytes_in_any_two_stages'],0)

    def test_direct_patch_matches_nested_transfer(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'transfer.zip'
            prefix='owp14_user12_o_preflight_job71153'
            patch=b'diff --git a/a b/a\n'
            digest=hashlib.sha256(patch).hexdigest()
            inner=io.BytesIO()
            with zipfile.ZipFile(inner,'w') as z:z.writestr('CASE_00001_O.patch',patch)
            blob=inner.getvalue()
            summary={'verified_archive_sha256':hashlib.sha256(blob).hexdigest(),
               'cases':{'1':{'case_id':1,'arm':'O','filename':'CASE_00001_O.patch','patch_applied':True,
                 'original_patch_sha256':digest,'original_patch_bytes':len(patch),
                 'git_apply_check_returncode':0,'git_apply_returncode':0}}}
            root=f'02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/{prefix}'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr(root+'/transfer.zip',blob)
                z.writestr(root+'/CASE_00001/CASE_00001_O.patch',patch)
            with zipfile.ZipFile(p) as z:
                self.assertEqual(compare_inner_transfer(z,prefix,summary)['direct_patch_matches'],1)
            with zipfile.ZipFile(p,'a') as z:
                z.writestr(root+'/CASE_00001/CASE_00001_O.patch_BAD',b'wrong')
            # Independent unrelated member cannot affect our verified direct patch mapping.
            with zipfile.ZipFile(p) as z:
                self.assertEqual(compare_inner_transfer(z,prefix,summary)['direct_patch_matches'],1)

    def test_nested_patch_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'transfer.zip'
            prefix='owp14_user14_w_preflight_job71208'
            patch=b'sample diff\n'
            inner=io.BytesIO()
            with zipfile.ZipFile(inner,'w') as z:z.writestr('CASE_00001_W.patch',patch)
            root=f'02_ALL_GENERATED_PATCHES/prevention_pilot_phase2/{prefix}'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr(root+'/transfer.zip',inner.getvalue())
                z.writestr(root+'/CASE_00001/CASE_00001_W.patch',patch+b'changed')
            summary={'verified_archive_sha256':hashlib.sha256(inner.getvalue()).hexdigest(),
               'cases':{'1':{'case_id':1,'arm':'W','filename':'CASE_00001_W.patch','patch_applied':True,
                 'original_patch_sha256':hashlib.sha256(patch).hexdigest(),'original_patch_bytes':len(patch),
                 'applycheck_returncode':0,'apply_returncode':0}}}
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(LineageError):compare_inner_transfer(z,prefix,summary)


if __name__=='__main__':unittest.main()
