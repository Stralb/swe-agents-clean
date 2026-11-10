"""Synthetic-only tests for a future frozen C7 archive intake."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from analysis.frozen_c6_c7_intake import (
    C6C7IntakeError, C7_ARCHIVE_NAME, C7_ARCHIVE_SHA256,
    C7_ARCHIVE_BYTES, C7_FILE_SIZES, main, source_inventory,
    verify_staged_c7,
)


def csv_bytes(header, rows):
    out = io.StringIO(newline="")
    wr = csv.writer(out)
    wr.writerow(header)
    wr.writerows(rows)
    return out.getvalue().encode()


def synthetic_parts():
    return {
        "C7_MATCHED_PATHWAY_MASTER_190.csv": csv_bytes(
            ["positive_case_id", "control_case_id", "pathway"],
            [["11", "21", "direct"], ["12", "22", "side_effect"]]),
        "C7_PATHWAY_STRATA_COMPARISON.csv": csv_bytes(["stratum", "n"], [["direct", "1"]]),
        "C7_VALIDATED_PROVENANCE_OVERLAY.csv": csv_bytes(["group", "n"], [["direct", "1"]]),
        "C7_SYNTHESIS_FINDINGS.csv": csv_bytes(["finding", "n"], [["association", "1"]]),
        "C7_REPORT.md": b"# Synthetic report\n",
    }


def make_archive(folder, parts=None, *, unsafe=None):
    parts = synthetic_parts() if parts is None else parts
    archive = folder / C7_ARCHIVE_NAME
    with tarfile.open(archive, "w:gz") as tf:
        directory = tarfile.TarInfo("C7_CONTROL_PATHWAY_INTEGRATION_v1.0/")
        directory.type = tarfile.DIRTYPE
        tf.addfile(directory)
        for name, data in parts.items():
            ti = tarfile.TarInfo("C7_CONTROL_PATHWAY_INTEGRATION_v1.0/" + name)
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        if unsafe == "traversal":
            data = b"bad"
            ti = tarfile.TarInfo("../bad.txt")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
        elif unsafe == "symlink":
            ti = tarfile.TarInfo("bad-link")
            ti.type = tarfile.SYMTYPE
            ti.linkname = "/etc/passwd"
            tf.addfile(ti)
    return archive


def verify_fixture(path, parts=None, **overrides):
    parts = synthetic_parts() if parts is None else parts
    pins = {"expected_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "expected_bytes": path.stat().st_size,
            "required_sizes": {k: len(v) for k, v in parts.items()},
            "expected_pairs": 2}
    pins.update(overrides)
    return verify_staged_c7(path, **pins)


class C6C7IntakeTests(unittest.TestCase):
    def test_expected_original_source_fingerprints(self):
        self.assertEqual(C7_ARCHIVE_BYTES, 106359)
        self.assertEqual(C7_ARCHIVE_SHA256,
            "976b523c3df347c82a81998a31585536e5dc826c9b61f55220190fa75b5f8273")
        self.assertEqual(C7_FILE_SIZES["C7_MATCHED_PATHWAY_MASTER_190.csv"], 112254)

    def test_inventory_explicitly_unreproduced(self):
        value = source_inventory()
        self.assertEqual(value["c6_source_reported_pairs"], 190)
        self.assertEqual(value["c6_source_reported_review_complete_pairs"], 189)
        self.assertEqual(value["c7_source_reported_mapped_pcs"], 416)
        self.assertFalse(value["statistical_results_reproduced"])
        self.assertFalse(value["c7_package_bytes_independently_verified"])

    def test_valid_synthetic_archive(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d))
            initial = path.read_bytes()
            result = verify_fixture(path)
            self.assertEqual(result["unique_positive_pairs"], 2)
            self.assertEqual(result["source_required_files_verified"], 5)
            self.assertEqual(path.read_bytes(), initial)
            self.assertFalse(result["statistical_p_values_recomputed"])

    def test_archive_contains_safe_directory_entry(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d))
            with tarfile.open(path, "r:gz") as tar:
                self.assertTrue(any(x.isdir() for x in tar.getmembers()))
            self.assertEqual(verify_fixture(path)["unique_positive_pairs"], 2)

    def test_different_digest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d))
            with self.assertRaisesRegex(C6C7IntakeError, "SHA-256"):
                verify_fixture(path, expected_sha256="0"*64)

    def test_different_length_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d))
            with self.assertRaisesRegex(C6C7IntakeError, "size"):
                verify_fixture(path, expected_bytes=1)

    def test_missing_required_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parts=synthetic_parts()
            del parts["C7_PATHWAY_STRATA_COMPARISON.csv"]
            path = make_archive(Path(d), parts)
            original_required = {k:len(v) for k,v in synthetic_parts().items()}
            with self.assertRaisesRegex(C6C7IntakeError, "missing a required"):
                verify_fixture(path, parts, required_sizes=original_required)

    def test_duplicate_positive_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parts = synthetic_parts()
            parts["C7_MATCHED_PATHWAY_MASTER_190.csv"] = csv_bytes(
                ["positive_case_id", "control_case_id"], [["11","21"],["11","22"]])
            with self.assertRaisesRegex(C6C7IntakeError, "reused"):
                verify_fixture(make_archive(Path(d),parts), parts)

    def test_duplicate_control_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parts = synthetic_parts()
            parts["C7_MATCHED_PATHWAY_MASTER_190.csv"] = csv_bytes(
                ["positive_case_id", "control_case_id"], [["11","21"],["12","21"]])
            with self.assertRaisesRegex(C6C7IntakeError, "reused"):
                verify_fixture(make_archive(Path(d),parts), parts)

    def test_wrong_pair_count_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d))
            with self.assertRaisesRegex(C6C7IntakeError, "pair denominator"):
                verify_fixture(path, expected_pairs=190)

    def test_untrusted_column_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            parts = synthetic_parts()
            parts["C7_MATCHED_PATHWAY_MASTER_190.csv"] = csv_bytes(
                ["positive", "control"], [["11","21"],["12","22"]])
            with self.assertRaisesRegex(C6C7IntakeError, "schema"):
                verify_fixture(make_archive(Path(d),parts), parts)

    def test_relative_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d), unsafe="traversal")
            with self.assertRaisesRegex(C6C7IntakeError, "Unsafe archive member path"):
                verify_fixture(path)

    def test_link_member_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = make_archive(Path(d), unsafe="symlink")
            with self.assertRaisesRegex(C6C7IntakeError, "links, devices"):
                verify_fixture(path)

    def test_source_path_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_archive(Path(d))
            alias = Path(d)/"alias.tar.gz"
            alias.symlink_to(p)
            with self.assertRaisesRegex(C6C7IntakeError,"symlink"):
                verify_fixture(alias)

    def test_public_cli_refuses_synthetic_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_archive(Path(d))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main(["verify-staged-c7",str(p)])
            self.assertEqual(result, 2)
            self.assertFalse(json.loads(output.getvalue())["independent_statistical_reproduction"])

    def test_source_only_cli_does_not_promote_results(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            code=main(["audit-recorded"])
        self.assertEqual(code,0)
        r=json.loads(out.getvalue())
        self.assertFalse(r["c6_statistical_tests_recomputed"])
        self.assertEqual(r["c7_source_reported_pairs"],190)


if __name__=="__main__":
    unittest.main()
