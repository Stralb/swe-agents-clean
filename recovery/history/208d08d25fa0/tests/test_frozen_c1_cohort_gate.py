"""Synthetic-only tests for standalone, original-frozen C1 cohort label audit."""
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

from analysis.cluster_stage_lineage import StageEvidenceError, load_recorded
from analysis.frozen_c1_cohort_gate import main, verify_c1_cases_only


def fixture(root: Path):
    path = root / "synthetic-c1.csv"
    data = copy.deepcopy(load_recorded())
    rows = [
        {
            "case_id": "10", "pr_id": "91", "repository": "synthetic/repo",
            "is_positive": "1", "complete_opportunity_signature": "codeql;semgrep",
        },
        {
            "case_id": "11", "pr_id": "92", "repository": "synthetic/repo",
            "is_positive": "0", "complete_opportunity_signature": "",
        },
        {
            "case_id": "12", "pr_id": "93", "repository": "synthetic/other",
            "is_positive": "0", "complete_opportunity_signature": "codeql",
        },
    ]
    write(path, data, rows)
    return path, data, rows


def write(path: Path, data: dict, rows):
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    meta = data["c1_scanner_opportunity"]
    meta["input_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    meta["input_bytes"] = path.stat().st_size


class FrozenC1StandaloneTests(unittest.TestCase):
    def test_readonly_original_c1_evidence_matches_c2_input_fingerprint(self):
        from analysis.cluster_stage_lineage import ROOT, load_recorded
        source = load_recorded()
        file = ROOT / "provenance" / "c1_cohort_readonly_audit_20261021.json"
        record = json.loads(file.read_text(encoding="utf-8"))
        self.assertEqual(record["schema_version"], 1)
        self.assertEqual(record["independently_observed_sha256"],
                         record["source_frozen_sha256"])
        self.assertEqual(record["source_frozen_sha256"],
                         source["c1_scanner_opportunity"]["input_sha256"])
        self.assertEqual(record["source_frozen_sha256"],
                         source["c2_matching"]["input_c1_expected_sha256"])
        self.assertEqual(record["bytes"],
                         source["c1_scanner_opportunity"]["input_bytes"])
        self.assertEqual(record["observed_case_rows"], 3809)
        self.assertEqual(record["distinct_numeric_case_ids"], 3809)
        self.assertEqual(record["stored_positive_labels"], 192)
        self.assertEqual(record["stored_negative_labels"], 3617)
        self.assertEqual(record["invalid_stored_labels"], 0)
        self.assertTrue(record["full_file_sha256_matched"])
        self.assertTrue(record["strictly_increasing_case_ids"])
        for field in (
            "original_c1_bytes_committed_to_git",
            "original_c1_label_correctness_rederived_from_sqlite",
            "final_aug29_sqlite_sha256_verified",
            "c1_to_c2_full_pair_membership_verified",
            "scanner_finding_validity_independently_verified",
            "statistical_estimates_reproduced",
        ):
            self.assertFalse(record[field])

    def test_valid_synthetic_c1_replays_labels_but_not_security_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, _ = fixture(Path(tmp))
            output = verify_c1_cases_only(path, data,
                                          expected_cases=3, expected_positives=1)
        self.assertEqual(output["status"],
                         "PASS_C1_BYTES_AND_FROZEN_LABEL_COUNTS_ONLY")
        self.assertEqual((output["case_rows"], output["distinct_case_ids"]),
                         (3, 3))
        self.assertEqual(output["source_recorded_positive_labels"], 1)
        self.assertEqual(output["source_recorded_negative_pool"], 2)
        self.assertTrue(output["sha256_verified_against_frozen_metadata"])
        self.assertFalse(output["positive_case_label_correctness_independently_verified"])
        self.assertFalse(output["final_sqlite_positive_set_recomputed"])
        self.assertFalse(output["original_scanners_reexecuted"])
        self.assertFalse(output["matched_pairs_recomputed"])
        self.assertFalse(output["causal_results_reproduced"])

    def test_original_expected_positive_denominator_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, _ = fixture(Path(tmp))
            with self.assertRaisesRegex(StageEvidenceError, "original count"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=2)

    def test_duplicate_case_id_fails_even_if_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, rows = fixture(Path(tmp))
            rows[1]["case_id"] = rows[0]["case_id"]
            write(path, data, rows)
            with self.assertRaisesRegex(StageEvidenceError, "duplicate"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_nonbinary_positive_indicator_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, rows = fixture(Path(tmp))
            rows[0]["is_positive"] = "True"
            write(path, data, rows)
            with self.assertRaisesRegex(StageEvidenceError, "not binary"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_positive_without_scanner_opportunity_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, rows = fixture(Path(tmp))
            rows[0]["complete_opportunity_signature"] = ""
            write(path, data, rows)
            with self.assertRaisesRegex(StageEvidenceError, "opportunity"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_duplicate_positive_opportunity_token_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, rows = fixture(Path(tmp))
            rows[0]["complete_opportunity_signature"] = "codeql;codeql"
            write(path, data, rows)
            with self.assertRaisesRegex(StageEvidenceError, "opportunity"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_missing_pr_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, rows = fixture(Path(tmp))
            rows[1]["pr_id"] = ""
            write(path, data, rows)
            with self.assertRaisesRegex(StageEvidenceError, "invalid PR ID"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_unchanged_sha_manifest_detects_byte_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, _ = fixture(Path(tmp))
            path.write_bytes(path.read_bytes().replace(b"synthetic/repo",
                                                        b"synthetic/REPO"))
            with self.assertRaisesRegex(StageEvidenceError, "SHA-256"):
                verify_c1_cases_only(path, data,
                                     expected_cases=3, expected_positives=1)

    def test_symlinked_c1_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, data, _ = fixture(Path(tmp))
            alias = Path(tmp) / "alias.csv"
            alias.symlink_to(path)
            with self.assertRaisesRegex(StageEvidenceError, "symlink"):
                verify_c1_cases_only(alias, data,
                                     expected_cases=3, expected_positives=1)

    def test_absent_original_csv_stays_blocked_in_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = main([str(Path(tmp) / "not-provided.csv")])
        self.assertEqual(status, 2)
        result = json.loads(out.getvalue())
        self.assertEqual(result["status"], "BLOCKED_C1_FILE_OR_FROZEN_LABELS")
        self.assertFalse(result["scanner_positive_set_reproduced"])


if __name__ == "__main__":
    unittest.main()
