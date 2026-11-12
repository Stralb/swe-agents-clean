"""Synthetic safety checks and recorded-summary checks; no Wits inputs in CI."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.c1_c2_late_issue_chronology_gate import (
    ChronologyCensusError,
    LEDGER,
    audit_recorded,
    indexed_pair_membership,
    main,
    verify_staged,
)


def fixture() -> dict:
    return json.loads(LEDGER.read_text(encoding="utf-8"))


class LateIssueChronologyTests(unittest.TestCase):
    def test_recorded_census_and_pair_intersections(self):
        out = audit_recorded()
        self.assertEqual(out["after_PR_open_case_count"], 49)
        self.assertEqual((out["positive_late"], out["negative_late"]), (4, 45))
        self.assertEqual((out["after_merge_case_count"], out["positive_after_merge"]),
                         (5, 0))
        self.assertEqual((out["C2_affected_pairs"], out["C2_both_late"]), (9, 1))
        self.assertEqual((out["C2_affected_pairs_tier_A"], out["C2_affected_pairs_tier_B"]),
                         (4, 5))
        self.assertEqual((out["C2_positive_late"], out["C2_control_late"]), (4, 6))
        self.assertFalse(out["final_august_SQLite_authenticated"])
        self.assertFalse(out["full_staged_C1_C2_bytes_authenticated"])

    def test_identical_case_lists_are_not_double_counted(self):
        src = fixture()
        src["chronology"]["late_created_case_ids"].append(5264)
        with self.assertRaisesRegex(ChronologyCensusError, "uniqueness"):
            audit_recorded(src)

    def test_wrong_cohort_membership_blocked(self):
        src = fixture()
        src["chronology"]["positive_late_case_ids"][-1] = 12335
        with self.assertRaisesRegex(ChronologyCensusError, "status"):
            audit_recorded(src)

    def test_false_source_authentication_claim_blocked(self):
        src = fixture()
        src["chronology_source"]["is_authenticated_final_august_database"] = True
        with self.assertRaisesRegex(ChronologyCensusError, "candidate DB"):
            audit_recorded(src)

    def test_source_sha_mutation_blocked(self):
        src = fixture()
        src["C1_source"]["expected_sha256_attested_in_earlier_recovery"] = "0" * 64
        with self.assertRaisesRegex(ChronologyCensusError, "SHA-256 expectations"):
            audit_recorded(src)

    def test_after_merge_case_wrong_label_blocked(self):
        src = fixture()
        src["chronology"]["after_pr_merged_case_ids"][0] = 5264
        with self.assertRaisesRegex(ChronologyCensusError, "status"):
            audit_recorded(src)

    def test_bad_affected_pair_classification_blocked(self):
        src = fixture()
        src["C2_matching"]["affected_pairs"][0]["control_case_id"] = 999999
        with self.assertRaisesRegex(ChronologyCensusError, "late membership"):
            audit_recorded(src)

    def test_reclassified_historical_data_blocked(self):
        src = fixture()
        src["science_limits"]["original_frozen_cohort_changed"] = True
        with self.assertRaisesRegex(ChronologyCensusError, "causal"):
            audit_recorded(src)

    def test_synthetic_pair_positivity_and_double_late(self):
        pos = {1: True, 2: False, 3: True, 4: False, 5: True, 6: False}
        pairs = [{"positive_case_id": 1, "control_case_id": 2, "match_tier": "A"},
                 {"positive_case_id": 3, "control_case_id": 4, "match_tier": "B"},
                 {"positive_case_id": 5, "control_case_id": 6, "match_tier": "B"}]
        out = indexed_pair_membership(pos, pairs, {1, 2, 4})
        self.assertEqual(out["pairs"], 3)
        self.assertEqual(out["tiers"], {"A": 1, "B": 2})
        self.assertEqual(out["late_positive_pair_count"], 1)
        self.assertEqual(out["late_control_pair_count"], 2)
        self.assertEqual(out["both_sides_late_count"], 1)
        self.assertEqual(len(out["affected"]), 2)

    def test_synthetic_wrong_positive_rejected(self):
        pos = {1: True, 2: True}
        pairs = [{"positive_case_id": 1, "control_case_id": 2, "match_tier": "A"}]
        with self.assertRaisesRegex(ChronologyCensusError, "status"):
            indexed_pair_membership(pos, pairs, {1})

    def test_synthetic_repeated_positive_rejected(self):
        pos = {1: True, 2: False, 3: False}
        pairs = [{"positive_case_id": 1, "control_case_id": 2, "match_tier": "A"},
                 {"positive_case_id": 1, "control_case_id": 3, "match_tier": "B"}]
        with self.assertRaisesRegex(ChronologyCensusError, "duplicate"):
            indexed_pair_membership(pos, pairs, {1})

    def test_staged_original_rejects_wrong_sha_even_with_same_filename(self):
        with tempfile.TemporaryDirectory() as base:
            c1, c2 = Path(base) / "C1_CASE_SCANNER_OPPORTUNITY_3809.csv", \
                     Path(base) / "C2_MATCHED_PAIRS_FROZEN.csv"
            c1.write_bytes(b"case_id,is_positive\n1,1\n")
            c2.write_bytes(b"positive_case_id,control_case_id\n1,2\n")
            with self.assertRaisesRegex(ChronologyCensusError, "byte size"):
                verify_staged(c1, c2)

    def test_staged_original_refuses_symlinks(self):
        with tempfile.TemporaryDirectory() as base:
            root = Path(base)
            real = root / "other.csv"
            real.write_text("junk", encoding="utf-8")
            link = root / "C1_CASE_SCANNER_OPPORTUNITY_3809.csv"
            link.symlink_to(real)
            with self.assertRaisesRegex(ChronologyCensusError, "symlinked"):
                verify_staged(link, real)

    def test_cli_reports_aggregate_without_private_rows(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main([]), 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(result["after_PR_open_case_count"], 49)
        self.assertNotIn("late_created_case_ids", buf.getvalue())
        self.assertNotIn("repository", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
