"""Exact integer outlier-deletion bounds, no sampled root labels."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

from analysis.d_lockfile_outlier_prevalence_bounds import (
    audit, compute_bounds, main
)


class LockfileOutlierBoundTests(unittest.TestCase):
    def test_conditional_D7_36_removal_extreme_bounds(self):
        out = compute_bounds("D7", {"H": 6, "T": 103, "M": 233},
                             "one_workflow", 36)
        self.assertEqual((out.remaining_roots, out.min_remaining_M,
                          out.max_remaining_M), (306, 197, 233))
        self.assertAlmostEqual(out.lower_M_fraction, 197/306)
        self.assertAlmostEqual(out.upper_M_fraction, 233/306)
        self.assertTrue(out.M_majority_robust)

    def test_conditional_D7_41_removal_extreme_bounds(self):
        out = compute_bounds("D7", {"H": 6, "T": 103, "M": 233},
                             "all_missing_export_chronology", 41)
        self.assertEqual((out.remaining_roots, out.min_remaining_M,
                          out.max_remaining_M), (301, 192, 233))
        self.assertAlmostEqual(out.lower_M_fraction, 192/301)
        self.assertAlmostEqual(out.upper_M_fraction, 233/301)
        self.assertTrue(out.M_majority_robust)

    def test_conditional_D_final_36_removal(self):
        out = compute_bounds("D-final", {"H": 5, "T": 103, "M": 234},
                             "one_workflow", 36)
        self.assertEqual((out.remaining_roots, out.min_remaining_M,
                          out.max_remaining_M), (306, 198, 234))
        self.assertTrue(out.M_majority_robust)

    def test_conditional_D_final_41_removal(self):
        out = compute_bounds("D-final", {"H": 5, "T": 103, "M": 234},
                             "all_missing_export_chronology", 41)
        self.assertEqual((out.remaining_roots, out.min_remaining_M,
                          out.max_remaining_M), (301, 193, 234))
        self.assertTrue(out.M_majority_robust)

    def test_complete_audit_has_four_source_reported_scenarios(self):
        out = audit()
        self.assertEqual(out["frozen_root_census"], 342)
        self.assertEqual(len(out["scenarios"]), 4)
        self.assertTrue(out["all_four_minimum_M_fractions_above_one_half"])
        self.assertTrue(all(x["M_majority_robust"] for x in out["scenarios"]))
        self.assertTrue(out["adversarial_bounds_not_statistical_CIs"])
        self.assertFalse(out["root_exclusions_applied_to_actual_dataset"])
        self.assertFalse(out["C6_190_paired_statistics_recomputed"])
        self.assertFalse(out["independent_root_observations_assumed"])

    def test_bound_if_remaining_M_is_not_majority_returns_false(self):
        out = compute_bounds("synthetic", {"H": 10, "T": 10, "M": 10},
                             "remove_10", 10)
        self.assertEqual((out.min_remaining_M, out.max_remaining_M), (0, 10))
        self.assertFalse(out.M_majority_robust)

    def test_bound_does_not_assume_all_removed_roots_are_T(self):
        out = compute_bounds("synthetic", {"H": 1, "T": 0, "M": 9},
                             "remove_six", 6)
        self.assertEqual((out.min_removed_M, out.max_removed_M), (5, 6))
        self.assertEqual((out.min_remaining_M, out.max_remaining_M), (3, 4))

    def test_wrong_route_counts_rejected(self):
        for labels in ({"M": 3, "T": 4},
                       {"H": 1, "T": -1, "M": 2},
                       {"H": 1.5, "T": 1, "M": 2}):
            with self.subTest(labels=labels):
                with self.assertRaisesRegex(ValueError, "nonnegative"):
                    compute_bounds("bad", labels, "bad", 1)

    def test_removal_that_drops_every_root_rejected(self):
        with self.assertRaisesRegex(ValueError, "preserve"):
            compute_bounds("bad", {"H": 1, "T": 1, "M": 1}, "bad", 3)

    def test_cli_reports_summary_not_fake_adjudication(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(), 0)
        data = json.loads(output.getvalue())
        self.assertFalse(data["historical_D_final_D7_complete_342_label_files_reauthenticated"])
        self.assertFalse(data["original_36_or_41_root_H_T_M_labels_authenticated"])
        self.assertNotIn("CROOT-13918-01", output.getvalue())


if __name__ == "__main__":
    unittest.main()
