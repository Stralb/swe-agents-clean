"""Independent, synthetic C2-only frozen pairing verification contracts."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.cluster_stage_lineage import StageEvidenceError
from analysis.frozen_c2_pair_gate import main, verify_c2_pairs_only
from tests.test_cluster_stage_lineage import sample_inputs


def rewrite(path: Path, data: dict, change):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames)
        rows = list(reader)
    change(rows)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    meta = data["c2_matching"]
    meta["matched_pairs_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    meta["matched_pairs_bytes"] = path.stat().st_size


class FrozenC2StandaloneTests(unittest.TestCase):
    def test_c2_readonly_attestation_matches_frozen_source_metadata(self):
        from analysis.cluster_stage_lineage import ROOT, load_recorded
        att = json.loads((ROOT / "provenance" /
            "c2_pair_readonly_audit_20261021.json").read_text(encoding="utf-8"))
        source = load_recorded()["c2_matching"]
        self.assertEqual(att["schema_version"], 1)
        self.assertEqual(att["observed_sha256"], att["source_expected_sha256"])
        self.assertEqual(att["observed_sha256"],
                         source["matched_pairs_sha256"])
        self.assertEqual(att["observed_bytes"],
                         source["matched_pairs_bytes"])
        self.assertEqual(att["matched_pairs"], 190)
        self.assertEqual(att["unique_positive_case_ids"], 190)
        self.assertEqual(att["unique_control_case_ids"], 190)
        self.assertEqual(att["tier_a_same_repo"], 115)
        self.assertEqual(att["tier_b_cross_repo"], 75)
        for field in ("original_c2_bytes_written_into_git",
                      "original_c1_bytes_fully_sha_verified",
                      "original_final_sqlite_sha_verified",
                      "optimizer_rerun", "substantive_outcomes_reproduced",
                      "causal_effects_estimated"):
            self.assertFalse(att[field])

    def test_standalone_tier_a_checks_synthetic_pair_without_c1_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            c1, c2, data = sample_inputs(Path(tmp))
            c1.unlink()  # The new validator MUST NOT require C1 file.
            answer = verify_c2_pairs_only(
                c2, data, expected_pairs=1, expected_same_repo=1)
        self.assertEqual(answer["status"],
                         "PASS_C2_BYTES_AND_INTERNAL_PAIR_RULES_ONLY")
        self.assertEqual(answer["tier_a_same_repo"], 1)
        self.assertEqual(answer["distinct_control_ids"], 1)
        self.assertTrue(answer["sha256_verified_against_frozen_metadata"])
        self.assertFalse(answer["c1_csv_sha256_verified"])
        self.assertFalse(answer["c1_positive_membership_verified"])
        self.assertFalse(answer["matcher_optimizer_rerun"])
        self.assertFalse(answer["scanner_findings_reproduced"])
        self.assertFalse(answer["causal_comparison_reproduced"])
        self.assertNotIn("positive_case_id", answer)

    def test_standalone_tier_b_cross_repo_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp), tier="B", control_id="3")
            answer = verify_c2_pairs_only(
                c2, data, expected_pairs=1, expected_same_repo=0)
        self.assertEqual(answer["tier_b_cross_repo"], 1)

    def test_modified_bytes_rejected_before_pair_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            c2.write_bytes(c2.read_bytes() + b"x")
            with self.assertRaises(StageEvidenceError):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=1)

    def test_modified_content_same_length_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            c2.write_bytes(c2.read_bytes().replace(b"8.5", b"9.5"))
            with self.assertRaisesRegex(StageEvidenceError, "SHA-256"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=1)

    def test_standalone_rejects_invented_tier_a_across_repositories(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp), tier="B", control_id="3")
            rewrite(c2, data, lambda rows: rows[0].update({
                "match_tier": "A", "same_repository": "0",
            }))
            with self.assertRaisesRegex(StageEvidenceError, "Tier A"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=1)

    def test_standalone_rejects_broken_same_repository_indicator(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            rewrite(c2, data, lambda rows: rows[0].update({
                "same_repository": "0"
            }))
            with self.assertRaisesRegex(StageEvidenceError, "same_repository bit"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=1)

    def test_duplicate_positive_or_control_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            rewrite(c2, data, lambda rows: rows.append(dict(rows[0])))
            with self.assertRaisesRegex(StageEvidenceError, "reused"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=2, expected_same_repo=2)

    def test_self_match_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            rewrite(c2, data, lambda rows: rows[0].update({
                "control_case_id": "1"
            }))
            with self.assertRaisesRegex(StageEvidenceError, "self-matched"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=1)

    def test_nonfinite_matching_time_refused(self):
        for bad in ("nan", "inf", "-inf", "91", "-1"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                _, c2, data = sample_inputs(Path(tmp))
                rewrite(c2, data, lambda rows: rows[0].update({
                    "abs_pr_time_days": bad
                }))
                with self.assertRaisesRegex(StageEvidenceError, "caliper"):
                    verify_c2_pairs_only(
                        c2, data, expected_pairs=1, expected_same_repo=1)

    def test_opportunity_signature_must_have_no_duplicate_or_empty_tokens(self):
        for bad in ("codeql;codeql", "codeql;", ""):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                _, c2, data = sample_inputs(Path(tmp))
                rewrite(c2, data, lambda rows: rows[0].update({
                    "positive_opportunity_signature": bad
                }))
                with self.assertRaisesRegex(StageEvidenceError, "Malformed"):
                    verify_c2_pairs_only(
                        c2, data, expected_pairs=1, expected_same_repo=1)

    def test_standalone_wrong_tier_counts_do_not_silently_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            with self.assertRaisesRegex(StageEvidenceError, "pair/tier totals"):
                verify_c2_pairs_only(
                    c2, data, expected_pairs=1, expected_same_repo=0)

    def test_missing_private_file_returns_blocked_without_exposing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                status = main([str(Path(tmp) / "missing-c2.csv")])
        self.assertEqual(status, 2)
        answer = json.loads(out.getvalue())
        self.assertEqual(answer["status"], "BLOCKED_C2_FILE_OR_PAIR_RULES")
        self.assertFalse(answer["original_scanner_results_reproduced"])

    def test_symlink_c2_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, c2, data = sample_inputs(Path(tmp))
            link = Path(tmp) / "alias-c2.csv"
            link.symlink_to(c2)
            with self.assertRaisesRegex(StageEvidenceError, "symlink"):
                verify_c2_pairs_only(
                    link, data, expected_pairs=1, expected_same_repo=1)


if __name__ == "__main__":
    unittest.main()
