"""Synthetic-only contract tests for the frozen 192 -> 455 -> 342 root gate."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.frozen_root_lineage_gate import (
    EXPECTED, FROZEN, RootLineageError, main, verify_root_lineage,
)

HEADERS = {
    "c1_positive": ["positive_case_id", "repository"],
    "c5_pc_to_root": ["PC ID", "Case ID", "Repository", "Root ID", "Root PC Count"],
    "c6_root_census": ["Root ID", "Case ID", "Repository", "PC Count", "Producing Change IDs"],
    "d1_root_index": ["Root ID", "Case ID", "Repository", "PC Count", "PC IDs"],
}

DATA = {
    "c1_positive": [
        {"positive_case_id": "11", "repository": "synthetic/one"},
        {"positive_case_id": "12", "repository": "synthetic/two"},
        {"positive_case_id": "13", "repository": "synthetic/three"},
    ],
    "c5_pc_to_root": [
        {"PC ID": "PC-1", "Case ID": "11", "Repository": "synthetic/one", "Root ID": "R1", "Root PC Count": "2"},
        {"PC ID": "PC-2", "Case ID": "11", "Repository": "synthetic/one", "Root ID": "R1", "Root PC Count": "2"},
        {"PC ID": "PC-3", "Case ID": "12", "Repository": "synthetic/two", "Root ID": "R2", "Root PC Count": "1"},
    ],
    "c6_root_census": [
        {"Root ID": "R1", "Case ID": "11", "Repository": "synthetic/one", "PC Count": "2", "Producing Change IDs": "PC-1; PC-2"},
        {"Root ID": "R2", "Case ID": "12", "Repository": "synthetic/two", "PC Count": "1", "Producing Change IDs": "PC-3"},
    ],
    "d1_root_index": [
        {"Root ID": "R1", "Case ID": "11", "Repository": "synthetic/one", "PC Count": "2", "PC IDs": "PC-1 | PC-2"},
        {"Root ID": "R2", "Case ID": "12", "Repository": "synthetic/two", "PC Count": "1", "PC IDs": "PC-3"},
    ],
}
FAKE_EXPECTED = {
    "positive_cases": 3, "mapped_cases": 2, "producing_changes": 3,
    "roots": 2, "unmapped_positive_case_ids": ["13"],
    "root_size_distribution": {"1": 1, "2": 1},
}


def fixture(directory: Path):
    paths, hashes = {}, {}
    for key, records in DATA.items():
        path = directory / (key + ".csv")
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS[key])
            writer.writeheader()
            writer.writerows(records)
        paths[key] = path
        hashes[key] = {"bytes": path.stat().st_size,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    return paths, hashes


def rerender(path: Path, key: str, hashes: dict, update) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    update(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS[key])
        writer.writeheader()
        writer.writerows(rows)
    hashes[key] = {"bytes": path.stat().st_size,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(paths: dict, hashes: dict, expected: dict = FAKE_EXPECTED) -> dict:
    return verify_root_lineage(paths["c1_positive"], paths["c5_pc_to_root"],
                               paths["c6_root_census"], paths["d1_root_index"],
                               fingerprints=hashes, expected=expected)


class FrozenRootLineageTests(unittest.TestCase):
    def test_hash_pinned_constants_are_source_counts(self):
        self.assertEqual(FROZEN["c1_positive"]["bytes"], 40984)
        self.assertEqual(FROZEN["c5_pc_to_root"]["bytes"], 194148)
        self.assertEqual(FROZEN["c6_root_census"]["bytes"], 179190)
        self.assertEqual(FROZEN["d1_root_index"]["bytes"], 66543)
        self.assertEqual(EXPECTED["positive_cases"], 192)
        self.assertEqual(EXPECTED["mapped_cases"], 191)
        self.assertEqual(EXPECTED["producing_changes"], 455)
        self.assertEqual(EXPECTED["roots"], 342)
        self.assertEqual(EXPECTED["unmapped_positive_case_ids"], ["17701"])

    def test_synthetic_full_membership_reconciles_readonly(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            before = {name: f.read_bytes() for name, f in p.items()}
            result = run(p, h)
            self.assertEqual(result["status"], "PASS_BYTE_VERIFIED_FROZEN_POSITIVE_TO_ROOT_CROSSWALK_ONLY")
            self.assertEqual(result["positive_roster_cases"], 3)
            self.assertEqual(result["positive_cases_with_roots"], 2)
            self.assertEqual(result["unmapped_positive_case_ids"], ["13"])
            self.assertEqual(result["unique_producing_changes"], 3)
            self.assertEqual(result["root_size_distribution"], {"1": 1, "2": 1})
            self.assertFalse(result["original_scanner_outcomes_recomputed"])
            self.assertFalse(result["statistical_results_reproduced"])
            self.assertNotIn("synthetic/one", json.dumps(result))
            self.assertEqual(before, {name: f.read_bytes() for name, f in p.items()})

    def test_fingerprint_violation_detects_same_length_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            path = p["c5_pc_to_root"]
            path.write_bytes(path.read_bytes().replace(b"PC-1", b"PC-9"))
            with self.assertRaisesRegex(RootLineageError, "SHA-256"):
                run(p, h)

    def test_root_membership_mismatch_c6_rejected_even_with_rehashed_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["c6_root_census"], "c6_root_census", h,
                     lambda rows: rows[0].update({"Producing Change IDs": "PC-1; PC-3"}))
            with self.assertRaisesRegex(RootLineageError, "membership/size"):
                run(p, h)

    def test_root_membership_mismatch_d1_rejected_even_with_rehashed_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["d1_root_index"], "d1_root_index", h,
                     lambda rows: rows[0].update({"PC IDs": "PC-1 | PC-3"}))
            with self.assertRaisesRegex(RootLineageError, "membership/size"):
                run(p, h)

    def test_duplicate_pc_and_root_cross_case_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["c5_pc_to_root"], "c5_pc_to_root", h,
                     lambda rows: rows[2].update({"PC ID": "PC-1"}))
            with self.assertRaisesRegex(RootLineageError, "repeated producing-change"):
                run(p, h)
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["c5_pc_to_root"], "c5_pc_to_root", h,
                     lambda rows: rows[2].update({"Root ID": "R1"}))
            with self.assertRaisesRegex(RootLineageError, "multiple cases"):
                run(p, h)

    def test_case_repository_disagreement_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["c1_positive"], "c1_positive", h,
                     lambda rows: rows[0].update({"repository": "synthetic/other"}))
            with self.assertRaisesRegex(RootLineageError, "repository outside"):
                run(p, h)

    def test_changed_missing_positive_set_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            exp = {**FAKE_EXPECTED, "unmapped_positive_case_ids": ["11"]}
            with self.assertRaisesRegex(RootLineageError, "unmapped set"):
                run(p, h, exp)

    def test_c6_duplicate_members_within_root_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            rerender(p["c6_root_census"], "c6_root_census", h,
                     lambda rows: rows[0].update({"Producing Change IDs": "PC-1; PC-1"}))
            with self.assertRaisesRegex(RootLineageError, "duplicate root PC membership"):
                run(p, h)

    def test_duplicate_headers_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            path = p["c1_positive"]
            body = path.read_text()
            path.write_text(body.replace("positive_case_id,repository", "positive_case_id,positive_case_id"))
            h["c1_positive"] = {"bytes": path.stat().st_size,
                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with self.assertRaisesRegex(RootLineageError, "duplicating required"):
                run(p, h)

    def test_symlink_staged_file_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            alias = Path(temp) / "alias.csv"
            alias.symlink_to(p["c1_positive"])
            p["c1_positive"] = alias
            with self.assertRaisesRegex(RootLineageError, "Symlink"):
                run(p, h)

    def test_public_cli_does_not_accept_fingerprint_overrides(self):
        with tempfile.TemporaryDirectory() as temp:
            p, h = fixture(Path(temp))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                status = main([str(p[key]) for key in (
                    "c1_positive", "c5_pc_to_root", "c6_root_census", "d1_root_index")])
            self.assertEqual(status, 2)
            msg = json.loads(buf.getvalue())
            self.assertEqual(msg["status"], "BLOCKED_FROZEN_ROOT_LINEAGE_INPUT")
            self.assertFalse(msg["scientific_replication_complete"])


if __name__ == "__main__":
    unittest.main()
