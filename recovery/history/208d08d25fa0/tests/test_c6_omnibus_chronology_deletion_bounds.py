"""Synthetic and source-indexed worst-case C6 multi-category deletion checks."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest

from analysis.c6_c7_indexed_omnibus import _load
from analysis.c6_omnibus_chronology_deletion_bounds import (
    OmnibusDeletionError, EXPECTED, audit, exhaustive_omnibus_removal, main,
)


class OriginalOmnibusRobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = audit(k=9)

    def test_instruction_specificity_all_allocations_are_defined(self):
        out = self.result["comparisons"]["Instruction specificity"]
        self.assertEqual(out["feasible_cell_removal_allocations"], 8006)
        self.assertEqual(out["original_fixed_rank_test_computable_allocations"], 8006)
        self.assertEqual(out["original_fixed_rank_test_uncomputable_empty_category_allocations"], 0)
        self.assertEqual(out["fixed_rank_allocations_nominal_p_at_least_0_05"], 0)
        self.assertAlmostEqual(out["max_p_fixed_rank"]["p_value"],
                               0.019269750388748126, places=12)
        self.assertIsNone(out["max_p_rank_adapted"])

    def test_goal_alignment_original_four_class_singularity_recorded(self):
        out = self.result["comparisons"]["Goal alignment"]
        self.assertEqual(out["feasible_cell_removal_allocations"], 2788)
        self.assertEqual(out["original_fixed_rank_test_computable_allocations"], 2136)
        self.assertEqual(out["original_fixed_rank_test_uncomputable_empty_category_allocations"], 652)
        self.assertEqual(out["fixed_rank_allocations_nominal_p_at_least_0_05"], 0)
        self.assertEqual(out["rank_adaptive_allocations_nominal_p_at_least_0_05"], 0)
        # Exact rational chi-square = 1127/135; independently checked
        # against SciPy chi2.sf and high-precision incomplete gamma.
        self.assertAlmostEqual(out["max_p_fixed_rank"]["chi_square"],
                               1127 / 135, places=12)
        self.assertAlmostEqual(out["max_p_fixed_rank"]["p_value"],
                               0.03933869747965109, places=12)
        self.assertAlmostEqual(out["max_p_rank_adapted"]["p_value"],
                               0.016841384073356665, places=8)
        self.assertEqual(out["max_p_rank_adapted"]["df"], 2)
        self.assertEqual(out["max_p_rank_adapted"]["alive_category_indices"], [0, 1, 2])

    def test_original_omnibus_pvalues_match_indexed_c6(self):
        i = self.result["comparisons"]["Instruction specificity"]
        g = self.result["comparisons"]["Goal alignment"]
        self.assertAlmostEqual(i["original_primary_omnibus"]["p_value"],
                               0.00052011700990405, places=12)
        self.assertAlmostEqual(g["original_primary_omnibus"]["p_value"],
                               0.00101867437927194, places=12)

    def test_provenance_is_not_laundered(self):
        out = self.result
        self.assertFalse(out["original_C6_paired_csv_sha256_authenticated"])
        self.assertFalse(out["original_frozen_final_sqlite_sha256_authenticated"])
        self.assertFalse(out["actual_affected_pair_categorical_labels_recovered"])
        self.assertFalse(out["original_nine_primary_familywise_postdeletion_adjustment_verified"])
        self.assertFalse(out["causal_inference_supported"])
        self.assertTrue(
            out["rank_adaptive_drop_zero_marginal_category_is_new_sensitivity_not_historical_method"])

    def test_zero_deletion_is_original_noncollapsed_table(self):
        for name, data in EXPECTED.items():
            got = exhaustive_omnibus_removal(data["counts"], 0)
            self.assertEqual(got["remaining_pairs"], 190)
            self.assertEqual(got["feasible_cell_removal_allocations"], 1)
            self.assertEqual(got["original_fixed_rank_test_uncomputable_empty_category_allocations"], 0)

    def test_invalid_deletions_are_blocked(self):
        m = EXPECTED["Instruction specificity"]["counts"]
        for n in (-1, 190, 191, 2.0, True):
            with self.subTest(n=n), self.assertRaises(OmnibusDeletionError):
                exhaustive_omnibus_removal(m, n)

    def test_tampered_indexed_matrix_rejected(self):
        data = _load()
        data["primary_categorical"]["Goal alignment"]["counts"][0][0] += 1
        with self.assertRaisesRegex(OmnibusDeletionError, "contingency changed"):
            audit(aggregate=data)

    def test_invalid_new_source_claim_rejected(self):
        data = _load()
        data["scientific_limits"]["staged_original_C6_C7_csv_sha256_verified"] = True
        with self.assertRaisesRegex(OmnibusDeletionError, "source bytes"):
            audit(aggregate=data)

    def test_main_outputs_aggregate_only_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["--remove-pairs", "9"]), 0)
        output = json.loads(buf.getvalue())
        self.assertIn("Goal alignment", output["comparisons"])
        self.assertEqual(output["candidate_sqlite_affected_pairs"], 9)
        self.assertNotIn("case_id", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
