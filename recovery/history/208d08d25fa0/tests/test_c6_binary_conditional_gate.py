"""Synthetic and recorded-aggregate checks only; never loads private Wits records."""
from __future__ import annotations

import contextlib
import io
import json
import unittest

from analysis.c6_binary_conditional_gate import (
    BinaryConsistencyError, audit_recorded, compatible_tables,
    count_for_rounded_rate, exact_two_sided_mcnemar, main,
)


class BinaryMathTests(unittest.TestCase):
    def test_exact_mcnemar_symmetry(self):
        self.assertEqual(exact_two_sided_mcnemar(30, 29), 1.0)
        self.assertEqual(exact_two_sided_mcnemar(29, 30), 1.0)

    def test_no_discordant_pairs(self):
        self.assertEqual(exact_two_sided_mcnemar(0, 0), 1.0)

    def test_all_discordant_one_way(self):
        self.assertEqual(exact_two_sided_mcnemar(0, 4), 0.125)

    def test_known_reconstructed_pvalues(self):
        self.assertAlmostEqual(exact_two_sided_mcnemar(31, 24),
                               0.4187541882690154, places=12)
        self.assertAlmostEqual(exact_two_sided_mcnemar(30, 39),
                               0.3355576182340152, places=12)

    def test_noninteger_or_negative_discordants_blocked(self):
        for x, y in ((-1, 0), (3.2, 4), (0, -1), (True, 0), (0, 201)):
            with self.subTest(x=x, y=y), self.assertRaises(BinaryConsistencyError):
                exact_two_sided_mcnemar(x, y)

    def test_rates_have_unique_integer_margins(self):
        self.assertEqual(count_for_rounded_rate(189, "28.6"), [54])
        self.assertEqual(count_for_rounded_rate(189, "24.9"), [47])
        self.assertEqual(count_for_rounded_rate(187, "70.1"), [131])
        self.assertEqual(count_for_rounded_rate(187, "74.9"), [140])

    def test_prior_percentages_impossible_at_n190(self):
        self.assertEqual(count_for_rounded_rate(190, "70.1"), [])
        self.assertEqual(count_for_rounded_rate(190, "74.9"), [])

    def test_invalid_percentage_or_pvalue_rejected(self):
        for r in ("NaN", "101.0", "-0.1", "50", "", "25.00"):
            with self.subTest(r=r), self.assertRaises(BinaryConsistencyError):
                count_for_rounded_rate(20, r)
        with self.assertRaises(BinaryConsistencyError):
            compatible_tables(n=10, positive_rate_1dp="30.0",
                              control_rate_1dp="20.0", p_3dp="0.9")
        with self.assertRaises(BinaryConsistencyError):
            compatible_tables(n=10, positive_rate_1dp="30.0",
                              control_rate_1dp="20.0", p_3dp="nan")

    def test_reported_review_table_is_unique_conditional_on_exact_test(self):
        out = compatible_tables(n=189, positive_rate_1dp="28.6",
                                control_rate_1dp="24.9", p_3dp="0.419")
        self.assertEqual(len(out), 1)
        self.assertEqual([out[0][x] for x in
                          ("both_yes", "positive_only", "control_only", "neither_yes")],
                         [23, 31, 24, 111])

    def test_reported_prior_activity_table_is_unique_conditional_on_exact_test(self):
        out = compatible_tables(n=187, positive_rate_1dp="70.1",
                                control_rate_1dp="74.9", p_3dp="0.336")
        self.assertEqual(len(out), 1)
        self.assertEqual([out[0][x] for x in
                          ("both_yes", "positive_only", "control_only", "neither_yes")],
                         [101, 30, 39, 17])

    def test_wrong_reported_p_not_laundered(self):
        out = compatible_tables(n=187, positive_rate_1dp="70.1",
                                control_rate_1dp="74.9", p_3dp="0.000")
        self.assertEqual(out, [])

    def test_provenance_flags_fail_closed(self):
        out = audit_recorded()
        self.assertTrue(out["controls_read_directly_from_original_Wits_C6_context"])
        self.assertFalse(out["positive_side_marginals_independently_recovered"])
        self.assertFalse(out["original_C6_paired_master_bytes_authenticated"])
        self.assertFalse(out["original_historical_test_formula_proven"])
        self.assertFalse(out["matched_pair_joints_independently_recovered"])
        self.assertFalse(out["original_C6_results_sample_size_187_confirmed"])
        self.assertTrue(out["comparisons"]["any_prior_repository_activity"]
                        ["historical_catalog_n_disagrees_with_effective_n"])
        self.assertFalse(out["comparisons"]["human_review"]
                         ["historical_catalog_n_disagrees_with_effective_n"])

    def test_cli_is_json_and_no_source_rows(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["--json"]), 0)
        result = json.loads(buf.getvalue())
        self.assertEqual(len(result["comparisons"]), 2)
        self.assertIn("CONDITIONAL", result["status"])


if __name__ == "__main__":
    unittest.main()
