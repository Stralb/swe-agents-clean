"""Recorded Wits chronology test: no cluster, GitHub or raw C1/C2 data access."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest

from analysis.full3809_event_order_gate import (
    EventOrderGateError, SOURCE, audit, main,
)


def fixtures():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


class Full3809EventOrderTests(unittest.TestCase):
    def test_source_recorded_cohort_and_chronology_counts(self):
        r = audit()
        self.assertEqual(r["original_C1_census_cases"], 3809)
        self.assertEqual(r["original_C1_positive_cases"], 192)
        self.assertEqual(r["original_C1_negative_cases"], 3617)
        self.assertEqual(r["candidate_SQLite_matched_records"], 3809)
        self.assertEqual(r["issue_created_after_pr_open"], 49)
        self.assertEqual(r["issue_created_after_pr_open_positive"], 4)
        self.assertEqual(r["issue_created_after_pr_open_negative"], 45)
        self.assertEqual(r["issue_created_after_pr_merge"], 5)
        self.assertEqual(r["issue_created_after_merge_positive"], 0)

    def test_matching_nine_pairs_four_positives_six_controls(self):
        r = audit()
        self.assertEqual(r["affected_matched_pairs"], 9)
        self.assertEqual(r["affected_matched_positive_cases"], 4)
        self.assertEqual(r["affected_matched_control_cases"], 6)
        self.assertEqual(r["affected_pairs_both_sides"], 1)

    def test_expected_percentages(self):
        r = audit()
        self.assertAlmostEqual(r["full_cohort_late_issue_fraction"], 49/3809)
        self.assertAlmostEqual(r["positive_late_issue_fraction"], 4/192)
        self.assertAlmostEqual(r["negative_late_issue_fraction"], 45/3617)

    def test_source_provenance_not_laundered(self):
        r = audit()
        self.assertFalse(r["final_frozen_SQLite_sha256_authenticated"])
        self.assertFalse(r["historical_C6_issue_content_asof_implementation_verified"])
        self.assertTrue(r["late_issues_do_not_prove_root_mechanism_explanations"])

    def test_mutated_c1_segment_fail(self):
        x = fixtures()
        x["original_C1_chunked_row_census"][1]["positive_records"] += 1
        with self.assertRaisesRegex(EventOrderGateError, "C1 rows"):
            audit(x)

    def test_removed_candidate_sqlite_range_fail(self):
        x = fixtures()
        x["sqlite_join_id_range_counts"][3]["n"] -= 1
        with self.assertRaisesRegex(EventOrderGateError, "SQLite"):
            audit(x)

    def test_added_late_id_without_census_fail(self):
        x = fixtures()
        x["issue_created_after_pr_open_case_ids"].append(49345)
        with self.assertRaisesRegex(EventOrderGateError, "late-issue"):
            audit(x)

    def test_added_postmerge_positive_case_is_disallowed(self):
        x = fixtures()
        x["issue_created_after_pr_merge_case_ids"].append(12334)
        x["issue_created_after_pr_merge_case_ids"].sort()
        x["sqlite_join_id_range_counts"][1]["after_merge"] += 1
        with self.assertRaisesRegex(EventOrderGateError, "[Aa]fter-merge"):
            audit(x)

    def test_missing_mixed_matched_pair_fails(self):
        x = fixtures()
        x["C2_affected_matched_pair_rows"].pop()
        with self.assertRaisesRegex(EventOrderGateError, "nine C2"):
            audit(x)

    def test_invalid_matched_control_membership(self):
        x = fixtures()
        x["C2_affected_matched_pair_rows"][0]["control"] = 11280
        with self.assertRaisesRegex(EventOrderGateError, "C2 late-side"):
            audit(x)

    def test_false_final_database_attestation_blocked(self):
        x = fixtures()
        x["source_provenance"]["this_query_independently_authenticates_final_20260829_sqlite_sha256"] = True
        with self.assertRaisesRegex(EventOrderGateError, "source-authentication"):
            audit(x)

    def test_false_original_C6_asof_issue_snapshot_blocked(self):
        x = fixtures()
        x["source_provenance"]["asof_issue_text_authenticated"] = True
        with self.assertRaisesRegex(EventOrderGateError, "source-authentication"):
            audit(x)

    def test_incorrect_C2_source_digest_blocked(self):
        x = fixtures()
        x["source_provenance"]["original_C2_sha256_expected_and_verified_in_separate_prior_run"] = "0"*64
        with self.assertRaisesRegex(EventOrderGateError, "C2"):
            audit(x)

    def test_false_automatic_exclusion_claim_is_blocked(self):
        x = fixtures()
        x["source_interpretation_flags"]["issue_created_after_PR_open_implies_no_later_PR_code_was_informed_by_issue"] = True
        with self.assertRaisesRegex(EventOrderGateError, "causal"):
            audit(x)

    def test_duplicate_case_id_blocked(self):
        x = fixtures()
        x["issue_created_after_pr_open_case_ids"][2] = x["issue_created_after_pr_open_case_ids"][1]
        with self.assertRaisesRegex(EventOrderGateError, "unique"):
            audit(x)

    def test_json_cli(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(buf.getvalue())["issue_created_after_pr_open"], 49)
        self.assertNotIn("source issue text", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
