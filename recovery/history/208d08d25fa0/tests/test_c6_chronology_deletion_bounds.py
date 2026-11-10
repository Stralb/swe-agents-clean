"""Worst-case deletion math uses synthetic and indexed aggregate cases only."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest

from analysis.c6_indexed_pair_bootstrap_ci import AGGREGATES, SOURCE
from analysis.c6_chronology_deletion_bounds import (
    DeletionBoundError, all_k_removal_outcomes, audit, main,
)


class ChronologyBoundsTests(unittest.TestCase):
    def test_synthetic_all_single_deletions_enumerated(self):
        out = all_k_removal_outcomes(3, 1, 1, 1)
        self.assertEqual(len(out), 3)
        self.assertEqual(
            {tuple(r[x] for x in ("removed_positive_only",
                                 "removed_control_only", "removed_neutral"))
             for r in out}, {(1, 0, 0), (0, 1, 0), (0, 0, 1)})
        self.assertEqual(max(x["exact_two_sided_binary_mcnemar_p"] for x in out), 1.0)

    def test_zero_deletions_identical_to_original(self):
        out = all_k_removal_outcomes(23, 50, 117, 0)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["surviving_n"], 190)
        self.assertAlmostEqual(out[0]["paired_difference_pp"], -100*27/190)

    def test_invalid_counts_fail_closed(self):
        for case in ((-1, 2, 3, 1), (0.0, 2, 3, 1), (2, 3, 4, -1),
                     (2, 3, 4, 9), (0, 0, 0, 0), (1, 1, 1, True)):
            with self.subTest(case=case), self.assertRaises(DeletionBoundError):
                all_k_removal_outcomes(*case)

    def test_all_three_categories_preserve_direction_and_nominal_significance(self):
        rows = {(x["variable"], x["category"]): x for x in audit()["rows"]}
        self.assertEqual(len(rows), 3)
        for result in rows.values():
            self.assertEqual(result["surviving_n"], 181)
            self.assertTrue(result["binary_direction_cannot_reverse"])
            self.assertTrue(result["nominal_0_05_significant_under_all_allocations"])
        self.assertAlmostEqual(
            rows[("Instruction specificity", "Explicit instruction")]
            ["worst_case_binary_mcnemar_p"], 0.0327657590988232, places=12)
        self.assertAlmostEqual(
            rows[("Instruction specificity", "Suggests solution")]
            ["worst_case_binary_mcnemar_p"], 0.013530986849218607, places=12)
        self.assertAlmostEqual(
            rows[("Goal alignment", "Aligned")]
            ["worst_case_binary_mcnemar_p"], 0.006610751152038574, places=12)

    def test_worst_case_deletions_favor_smaller_discordant_imbalance(self):
        rows = {(x["variable"], x["category"]): x for x in audit()["rows"]}
        self.assertEqual(
            rows[("Instruction specificity", "Explicit instruction")]
            ["worst_case_allocation"]["removed_control_only"], 9)
        self.assertEqual(
            rows[("Instruction specificity", "Suggests solution")]
            ["worst_case_allocation"]["removed_positive_only"], 9)
        self.assertEqual(
            rows[("Goal alignment", "Aligned")]
            ["worst_case_allocation"]["removed_control_only"], 9)

    def test_source_provenance_and_denominators_remain_unverified(self):
        x = audit()
        self.assertFalse(x["historical_C6_source_bytes_authenticated"])
        self.assertFalse(x["candidate_snapshot_exact_final_August_DB_authenticated"])
        self.assertFalse(x["specific_chronology_affected_pair_outcomes_recovered"])
        self.assertFalse(x["historical_omnibus_Stuart_Maxwell_after_deletion_recomputed"])
        self.assertTrue(x["posthoc_selected_binary_indicators_not_preregistered_family"])

    def test_modified_aggregate_fails(self):
        original = json.loads(AGGREGATES.read_text())
        original["primary_categorical"]["Instruction specificity"]["counts"][0][0] += 1
        with self.assertRaisesRegex(DeletionBoundError, "counts drifted"):
            audit(aggregates=original)

    def test_false_source_authentication_is_blocked(self):
        original = json.loads(SOURCE.read_text())
        original["original_source_C6_file_bytes_authenticated"] = True
        with self.assertRaisesRegex(DeletionBoundError, "provenance"):
            audit(source=original)

    def test_custom_removal_count(self):
        self.assertEqual(audit(k=0)["rows"][0]["surviving_n"], 190)
        self.assertEqual(audit(k=2)["rows"][0]["surviving_n"], 188)

    def test_json_cli_uses_aggregate_only(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(["--remove-pairs", "9"]), 0)
        obj = json.loads(buf.getvalue())
        self.assertEqual(obj["candidate_snapshot_affected_pairs"], 9)
        self.assertEqual(len(obj["rows"]), 3)


if __name__ == "__main__":
    unittest.main()
