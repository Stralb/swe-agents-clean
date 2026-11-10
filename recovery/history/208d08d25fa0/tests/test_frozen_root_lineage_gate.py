"""Synthetic only. Never opens original research artifacts or Wits."""
from __future__ import annotations
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from analysis.frozen_root_lineage_gate import (
    EXPECTED, FROZEN, RootLineageError, main, verify_root_lineage
)

HEADERS = {
    "c1_positive": ["positive_case_id", "repository"],
    "c5_pc_to_root": ["PC ID", "Case ID", "Repository", "Root ID", "Root PC Count"],
    "c6_root_census": ["Root ID", "Case ID", "Repository", "PC Count", "Producing Change IDs"],
    "d1_root_index": ["Root ID", "Case ID", "Repository", "PC Count", "PC IDs"],
}
RECORDS = {
    "c1_positive": [
        ["11", "synthetic/a"], ["12", "synthetic/b"], ["13", "synthetic/c"]],
    "c5_pc_to_root": [
        ["PC1", "11", "synthetic/a", "R1", "2"],
        ["PC2", "11", "synthetic/a", "R1", "2"],
        ["PC3", "12", "synthetic/b", "R2", "1"]],
    "c6_root_census": [
        ["R1", "11", "synthetic/a", "2", "PC1; PC2"],
        ["R2", "12", "synthetic/b", "1", "PC3"]],
    "d1_root_index": [
        ["R1", "11", "synthetic/a", "2", "PC1 | PC2"],
        ["R2", "12", "synthetic/b", "1", "PC3"]],
}
FAKE_EXPECTED = {
    "positive_cases": 3, "mapped_cases": 2,
    "producing_changes": 3, "roots": 2,
    "unmapped_positive_case_ids": ["13"],
    "root_size_distribution": {"1": 1, "2": 1},
}


def write_fixture(folder, data=None):
    paths, hashes = {}, {}
    for name, columns in HEADERS.items():
        p = folder / (name + ".csv")
        with p.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(columns)
            w.writerows((data or RECORDS)[name])
        paths[name] = p
        hashes[name] = {"bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    return paths, hashes


def call(paths, hashes, expected=None):
    return verify_root_lineage(paths["c1_positive"], paths["c5_pc_to_root"],
        paths["c6_root_census"], paths["d1_root_index"],
        fingerprints=hashes, expected=FAKE_EXPECTED if expected is None else expected)


class RootCrosswalkSyntheticTests(unittest.TestCase):
    def test_frozen_constants_are_pinned(self):
        self.assertEqual([FROZEN[k]["bytes"] for k in HEADERS],
                         [40984, 194148, 179190, 66543])
        self.assertEqual([EXPECTED[k] for k in
                          ("positive_cases", "mapped_cases", "producing_changes", "roots")],
                         [192, 191, 455, 342])

    def test_exact_fixture_passes_without_writes(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            before = {k: p.read_bytes() for k, p in paths.items()}
            out = call(paths, hashes)
            self.assertEqual(out["positive_cases_with_roots"], 2)
            self.assertEqual(out["unique_producing_changes"], 3)
            self.assertEqual(out["unique_roots"], 2)
            self.assertFalse(out["statistical_results_reproduced"])
            self.assertEqual(before, {k: p.read_bytes() for k, p in paths.items()})

    def test_wrong_digest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            paths["c1_positive"].write_bytes(paths["c1_positive"].read_bytes()+b"x")
            with self.assertRaises(RootLineageError):
                call(paths, hashes)

    def test_tamper_same_length_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            p = paths["c5_pc_to_root"]
            p.write_bytes(p.read_bytes().replace(b"PC1", b"PC9"))
            with self.assertRaisesRegex(RootLineageError, "SHA-256"):
                call(paths, hashes)

    def test_duplicate_pc_rejected_even_if_rehashed(self):
        data = copy.deepcopy(RECORDS)
        data["c5_pc_to_root"][2][0] = "PC1"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "reused producing-change"):
                call(paths, hashes)

    def test_cross_case_root_rejected(self):
        data = copy.deepcopy(RECORDS)
        data["c5_pc_to_root"][2][3] = "R1"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "multiple cases"):
                call(paths, hashes)

    def test_c6_pc_membership_rejected(self):
        data = copy.deepcopy(RECORDS)
        data["c6_root_census"][0][-1] = "PC1; PC3"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "membership/size"):
                call(paths, hashes)

    def test_d1_pc_membership_rejected(self):
        data = copy.deepcopy(RECORDS)
        data["d1_root_index"][0][-1] = "PC1 | PC3"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "membership/size"):
                call(paths, hashes)

    def test_duplicate_pc_within_index_rejected(self):
        data = copy.deepcopy(RECORDS)
        data["c6_root_census"][0][-1] = "PC1; PC1"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "duplicate PC"):
                call(paths, hashes)

    def test_positive_case_repo_disagreement_rejected(self):
        data = copy.deepcopy(RECORDS)
        data["c1_positive"][0][1] = "synthetic/other"
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d), data)
            with self.assertRaisesRegex(RootLineageError, "repository not in positive"):
                call(paths, hashes)

    def test_missing_positive_set_is_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            wrong = dict(FAKE_EXPECTED, unmapped_positive_case_ids=["11"])
            with self.assertRaisesRegex(RootLineageError, "Frozen lineage count"):
                call(paths, hashes, wrong)

    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            alias = Path(d) / "alias.csv"
            alias.symlink_to(paths["c1_positive"])
            paths["c1_positive"] = alias
            with self.assertRaisesRegex(RootLineageError, "Symlink"):
                call(paths, hashes)

    def test_public_cli_rejects_synthetic_without_override(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([str(paths[k]) for k in HEADERS])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(out.getvalue())["scientific_replication_complete"])

    def test_duplicate_column_names_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            paths, hashes = write_fixture(Path(d))
            p = paths["c1_positive"]
            p.write_bytes(p.read_bytes().replace(b"positive_case_id,repository",
                                                 b"positive_case_id,positive_case_id"))
            hashes["c1_positive"] = {"bytes": p.stat().st_size,
                                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(RootLineageError, "Invalid required"):
                call(paths, hashes)


if __name__ == "__main__":
    unittest.main()
