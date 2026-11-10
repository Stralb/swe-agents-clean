"""Synthetic-only verification; no original cluster CSVs or database access."""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from analysis.frozen_root_crosswalk_gate import (
    CrosswalkError, verify_frozen_root_chain,
)

HEADERS = {
    "c1_positive": ["positive_case_id", "repository"],
    "c5_pc_root": ["PC ID", "Case ID", "Repository", "Root ID", "Root PC Count"],
    "c6_roots": ["Root ID", "Case ID", "Repository", "PC Count", "Producing Change IDs"],
    "d1_root_index": ["Root ID", "Case ID", "Repository", "PC Count", "PC IDs"],
}
DATA = {
    "c1_positive": [
        ["11", "fixture/repo-1"], ["12", "fixture/repo-2"], ["13", "fixture/repo-3"],
    ],
    "c5_pc_root": [
        ["P1", "11", "fixture/repo-1", "R11", "2"],
        ["P2", "11", "fixture/repo-1", "R11", "2"],
        ["P3", "12", "fixture/repo-2", "R12", "1"],
    ],
    "c6_roots": [
        ["R11", "11", "fixture/repo-1", "2", "P1; P2"],
        ["R12", "12", "fixture/repo-2", "1", "P3"],
    ],
    "d1_root_index": [
        ["R11", "11", "fixture/repo-1", "2", "P1 | P2"],
        ["R12", "12", "fixture/repo-2", "1", "P3"],
    ],
}
COUNTS = {"positives": 3, "mapped_cases": 2, "pcs": 3,
          "roots": 2, "unmapped": {"13"}, "root_sizes": {1: 1, 2: 1}}


def write_fixture(root: Path, rows: dict) -> tuple[dict, dict]:
    paths, specs = {}, {}
    for name, data in rows.items():
        path = root / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS[name])
            writer.writerows(data)
        paths[name] = path
        body = path.read_bytes()
        specs[name] = (len(body), hashlib.sha256(body).hexdigest())
    return paths, specs


class FrozenRootCrosswalkTests(unittest.TestCase):
    def run_with(self, mutate=None, *, expected=None):
        with tempfile.TemporaryDirectory() as tmp:
            data = {key: [r.copy() for r in records] for key, records in DATA.items()}
            if mutate:
                mutate(data)
            paths, specs = write_fixture(Path(tmp), data)
            return verify_frozen_root_chain(
                paths, specs=specs, expected=expected or COUNTS,
            )

    def test_exact_synthetic_chain(self):
        result = self.run_with()
        self.assertEqual(result["status"], "PASS_FROZEN_C1_TO_C5_C6_D1_MEMBERSHIP_ONLY")
        self.assertEqual(result["distinct_producing_changes"], 3)
        self.assertEqual(result["distinct_root_decisions"], 2)
        self.assertEqual(result["unmapped_positive_ids"], ["13"])
        self.assertFalse(result["scanner_results_reproduced"])
        self.assertFalse(result["final_aug29_sqlite_verified"])

    def test_repeated_pc_rejected(self):
        with self.assertRaisesRegex(CrosswalkError, "duplicate/missing PC"):
            self.run_with(lambda d: d["c5_pc_root"][1].__setitem__(0, "P1"))

    def test_c5_root_cannot_span_workflows(self):
        with self.assertRaisesRegex(CrosswalkError, "crosses workflow"):
            self.run_with(lambda d: d["c5_pc_root"][1].__setitem__(1, "12"))

    def test_c6_root_pc_membership_mismatch(self):
        with self.assertRaisesRegex(CrosswalkError, "disagrees with C5"):
            self.run_with(lambda d: d["c6_roots"][0].__setitem__(4, "P1; X9"))

    def test_d1_missing_member(self):
        with self.assertRaisesRegex(CrosswalkError, "disagrees with C5"):
            self.run_with(lambda d: d["d1_root_index"][0].__setitem__(4, "P1"))

    def test_c1_positive_repo_mismatch(self):
        with self.assertRaisesRegex(CrosswalkError, "repository differs"):
            self.run_with(lambda d: d["c1_positive"][0].__setitem__(1, "other/repo"))

    def test_c1_missing_positive_violates_population(self):
        with self.assertRaisesRegex(CrosswalkError, "population mismatch"):
            self.run_with(lambda d: d["c1_positive"].pop())

    def test_reject_corrupted_file_even_if_csv_parses(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, specs = write_fixture(Path(tmp), DATA)
            paths["c5_pc_root"].write_bytes(paths["c5_pc_root"].read_bytes() + b"\n")
            with self.assertRaisesRegex(CrosswalkError, "byte length"):
                verify_frozen_root_chain(paths, specs=specs, expected=COUNTS)

    def test_reject_symlink_to_frozen_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, specs = write_fixture(Path(tmp), DATA)
            link = Path(tmp) / "linked-c1.csv"
            link.symlink_to(paths["c1_positive"])
            paths["c1_positive"] = link
            with self.assertRaisesRegex(CrosswalkError, "symlink"):
                verify_frozen_root_chain(paths, specs=specs, expected=COUNTS)

    def test_reject_root_pc_count_discrepancy(self):
        with self.assertRaisesRegex(CrosswalkError, "root-count annotations"):
            self.run_with(lambda d: d["c5_pc_root"][0].__setitem__(4, "3"))


if __name__ == "__main__":
    unittest.main()
