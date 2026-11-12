"""Reproducible source-indexed aggregate arithmetic tests; no private source data."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest
from analysis.c6_primary_family_audit import (
    FamilyAuditError, ALPHA, _read, INDEXED, AGGREGATES, CATALOG,
    audit, benjamini_hochberg, holm, main,
)


def inputs():
    return dict(indexed=copy.deepcopy(_read(INDEXED)),
                aggregates=copy.deepcopy(_read(AGGREGATES)),
                catalog=copy.deepcopy(_read(CATALOG)))


class MultiplicityTests(unittest.TestCase):
    def test_holm_known_reference(self):
        got = holm({"a": 0.01, "b": 0.04, "c": 0.05})
        self.assertEqual(got, {"a": 0.03, "b": 0.08, "c": 0.08})

    def test_bh_known_reference(self):
        got = benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.05})
        self.assertAlmostEqual(got["a"], 0.03)
        self.assertAlmostEqual(got["b"], 0.05)
        self.assertAlmostEqual(got["c"], 0.05)

    def test_holm_order_and_equal_p_ties(self):
        self.assertEqual(holm({"c": .03, "a": .01, "b": .01}),
                         {"a": .03, "b": .03, "c": .03})

    def test_bh_order_and_equal_p_ties(self):
        a = benjamini_hochberg({"a": .01, "b": .01, "c": .03})
        for v in a.values():
            self.assertAlmostEqual(v, .015 if v < .03 else .03)

    def test_invalid_pvalues_rejected(self):
        for wrong in ({}, {"x": float('nan')}, {"x": -0.1},
                      {"x": 1.01}, {"x": "0.001"}, {"": .5}, {"x": float('inf')}):
            with self.subTest(values=wrong), self.assertRaises(FamilyAuditError):
                holm(wrong)

    def test_nine_primary_holm_source_reported_family(self):
        result = audit()
        adj = result["reported_pvalues_holm"]
        self.assertEqual(result["historical_primary_family_count"], 9)
        self.assertEqual(result["holm_significant_at_0_05"],
                         ["issue_instruction_specificity", "pr_goal_alignment"])
        self.assertAlmostEqual(adj["issue_instruction_specificity"], 0.00468)
        self.assertAlmostEqual(adj["pr_goal_alignment"], 0.008)
        self.assertGreater(adj["issue_purpose"], .05)

    def test_nine_primary_bh_reported_family(self):
        v = audit()["reported_pvalues_bh_fdr"]
        self.assertAlmostEqual(v["issue_instruction_specificity"], .0045)
        self.assertAlmostEqual(v["pr_goal_alignment"], .0045)
        self.assertTrue(all(v[k] > .05 for k in v if k not in
                            ("issue_instruction_specificity", "pr_goal_alignment")))

    def test_significance_robust_to_pvalue_display_rounding(self):
        z = audit()["conservative_display_rounding_check"]
        for k in ("issue_instruction_specificity", "pr_goal_alignment"):
            self.assertLess(9*z[k]["upper_p_from_display"], ALPHA)
        for k in z:
            if k not in ("issue_instruction_specificity", "pr_goal_alignment"):
                self.assertGreater(z[k]["lower_p_from_display"], ALPHA)

    def test_mixed_evidence_holm_uses_five_exact_indexed_tests(self):
        z = audit()
        h = z["mixed_evidence_holm_sensitivity_five_exact_four_reported"]
        self.assertAlmostEqual(h["issue_instruction_specificity"],
                               9*0.00052011700990405, places=11)
        self.assertAlmostEqual(h["pr_goal_alignment"],
                               8*0.00101867437927194, places=11)

    def test_same_repository_sensitivity_not_merged_into_primary_family(self):
        z = audit()
        self.assertEqual(len(z["reported_pvalues_holm"]), 9)
        self.assertEqual(z["tier_a_nominal_pvalues_reported_only"]["n_pairs"], 115)
        self.assertAlmostEqual(z["tier_a_specificity_hypothetical_nine_test_bonferroni"], .05805)
        self.assertFalse(z["historical_familywise_adjustment_originally_preregistered"])


class CategoryReconciliationTests(unittest.TestCase):
    def test_seven_category_groupings_37_categories_all_match(self):
        z = audit()
        self.assertEqual(z["observed_category_effect_rows_reconciled"], 37)
        self.assertEqual(len(z["indexed_category_details"]), 7)
        self.assertEqual(z["indexed_category_details"]["Requester association"]["n_pairs"],189)
        self.assertTrue(all(x["n_pairs"] == 190 for name,x in z["indexed_category_details"].items()
                            if name != "Requester association"))

    def test_original_review_missing_denominator_kept(self):
        z = audit()
        self.assertFalse(z["four_remaining_primary_statistics_independently_recomputed"])
        self.assertFalse(z["historical_semantic_labels_and_original_C6_bytes_authenticated"])
        self.assertFalse(z["historical_repo_blocked_resampling_recomputed"])

    def test_bad_category_effect_count_rejected(self):
        x = inputs()
        x["indexed"]["category_effect_counts"]["Instruction specificity"]["Explicit instruction"][0] += 1
        with self.assertRaisesRegex(FamilyAuditError,"category-level effect.*disagree"):
            audit(**x)

    def test_primary_category_deleted_rejected(self):
        x = inputs()
        del x["indexed"]["category_effect_counts"]["Issue purpose"]["Feature / capability addition"]
        with self.assertRaisesRegex(FamilyAuditError,"category coverage"):
            audit(**x)

    def test_secondary_matrix_tamper_rejected(self):
        x = inputs()
        x["indexed"]["secondary_contingency"]["Requester association"]["counts"][0][0] += 1
        with self.assertRaisesRegex(FamilyAuditError,"denominator"):
            audit(**x)

    def test_source_recorded_pvalue_tamper_rejected(self):
        x = inputs()
        x["indexed"]["historical_primary_pvalues"][2]["p_reported"] = 0.03
        with self.assertRaisesRegex(FamilyAuditError,"p-value.*drift"):
            audit(**x)

    def test_missing_human_review_count_not_190(self):
        x = inputs()
        for y in x["indexed"]["historical_primary_pvalues"]:
            if y["name"] == "human_review": y["n_pairs_reported"] = 190
        with self.assertRaisesRegex(FamilyAuditError,"paired denominator"):
            audit(**x)

    def test_missing_review_one_intentional(self):
        x = inputs()
        x["catalog"]["preserved_historical_reports"]["c6_human_review_missing"] = 0
        with self.assertRaisesRegex(FamilyAuditError,"review"):
            audit(**x)

    def test_duplicate_hypothesis_rejected(self):
        x = inputs()
        x["indexed"]["historical_primary_pvalues"][1]["name"] = "issue_instruction_specificity"
        with self.assertRaisesRegex(FamilyAuditError,"Duplicate"):
            audit(**x)

    def test_original_source_hash_provenance_not_laundered(self):
        x = inputs()
        x["indexed"]["source_representation"]["source_C6_original_file_bytes_authenticated"] = True
        with self.assertRaisesRegex(FamilyAuditError,"source-byte"):
            audit(**x)

    def test_repo_sensitive_test_not_claimed_to_be_reproduced(self):
        x = inputs()
        x["indexed"]["source_reported_tier_a_sensitivity"]["status"] = "FULLY_REPRODUCED"
        with self.assertRaisesRegex(FamilyAuditError,"Tier-A"):
            audit(**x)

    def test_cli_is_read_only_and_aggregate_only(self):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            code = main(["--json"])
        self.assertEqual(code, 0)
        obj = json.loads(f.getvalue())
        self.assertEqual(obj["observed_category_effect_rows_reconciled"], 37)
        self.assertNotIn("case_id", f.getvalue())
        self.assertFalse(obj["historical_semantic_labels_and_original_C6_bytes_authenticated"])


if __name__ == "__main__":
    unittest.main()
