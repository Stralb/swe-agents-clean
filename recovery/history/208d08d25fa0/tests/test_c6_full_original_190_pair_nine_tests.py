"""Synthetic replay of paired C6 statistics; original 98,431 bytes absent in CI."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from analysis.c6_full_original_190_pair_nine_tests import (
    EXPECTED,
    ORIGINAL_SIZE,
    PairedReplayError,
    audit_original,
    binary_mcnemar,
    binom_exact_mcnemar,
    chisq_sf,
    solve,
    stuart_maxwell,
    wilcoxon_delay,
)


def binrows(yy: int, yn: int, ny: int, nn: int) -> list[dict]:
    return ([{"p":"Yes","c":"Yes"}]*yy +
            [{"p":"Yes","c":"No"}]*yn +
            [{"p":"No","c":"Yes"}]*ny +
            [{"p":"No","c":"No"}]*nn)


class OriginalC6NineTestRegression(unittest.TestCase):
    def test_original_report_test_family_names_pinned(self):
        self.assertEqual(len(EXPECTED),9)
        self.assertEqual(EXPECTED["Formal human review before merge"][0],189)
        self.assertEqual(EXPECTED["Any requester prior repo activity"][0],187)

    def test_original_mcnemar_human_review_discordances(self):
        r = binary_mcnemar(binrows(23,31,24,111),"p","c")
        self.assertEqual(r["n"],189)
        self.assertEqual(r["positive_yes"],54)
        self.assertEqual(r["control_yes"],47)
        self.assertAlmostEqual(r["p_value"],0.4187541882690154,places=14)
        self.assertAlmostEqual(r["effect_value"],7/189,places=14)

    def test_original_mcnemar_prior_activity_discordances(self):
        r = binary_mcnemar(binrows(101,30,39,17),"p","c")
        self.assertEqual(r["n"],187)
        self.assertAlmostEqual(r["p_value"],0.3355576182340152,places=14)
        self.assertEqual(r["positive_yes"],131)
        self.assertEqual(r["control_yes"],140)

    def test_original_mcnemar_same_author(self):
        r = binary_mcnemar(binrows(39,30,29,92),"p","c")
        self.assertEqual(r["n"],190)
        self.assertEqual(r["p_value"],1)
        self.assertAlmostEqual(r["effect_value"],1/190)

    def test_missing_binary_one_side_excluded_not_negative(self):
        sample=binrows(1,1,1,1) + [{"p":"No","c":""}]
        for i,row in enumerate(sample,1):
            row["pair_index"]=str(i)
        r=binary_mcnemar(sample,"p","c")
        self.assertEqual(r["n"],4)
        self.assertEqual(r["excluded_pair_ids"],[5])
        self.assertEqual(r["both_no"],1)

    def test_chi2_reference_values_from_original_report(self):
        tests=[
            (9.31354906196363,5,0.0971925657089748),
            (15.12291350531108,2,0.000520117009904),
            (16.22707423580786,3,0.0010186743792719),
            (10.124067054069648,6,0.1195235832394017),
            (7.021980760604094,5,0.2190106974324261),
        ]
        for statistic,df,expected in tests:
            with self.subTest(df=df,statistic=statistic):
                self.assertAlmostEqual(chisq_sf(statistic,df),expected,places=12)

    def test_two_category_stuart_maxwell_matches_mcnemar_chisquare(self):
        rows=( [{"p":"A","c":"A"}]*5 +
               [{"p":"A","c":"B"}]*4 +
               [{"p":"B","c":"A"}]*1 +
               [{"p":"B","c":"B"}]*5 )
        r=stuart_maxwell(rows,"p","c")
        self.assertEqual(r["n"],15)
        self.assertEqual(r["df"],1)
        self.assertAlmostEqual(r["statistic"],9/5)
        self.assertAlmostEqual(r["effect_value"],3/15)
        self.assertAlmostEqual(r["p_value"],math.erfc(math.sqrt(.9)))

    def test_symmetrical_categorical_table_has_zero_statistic(self):
        r=stuart_maxwell(
            ([{"p":"A","c":"A"}]*4 +
             [{"p":"A","c":"B"}]*2 +
             [{"p":"B","c":"A"}]*2 +
             [{"p":"B","c":"B"}]*3),"p","c")
        self.assertEqual(r["statistic"],0)
        self.assertEqual(r["p_value"],1)
        self.assertEqual(r["effect_value"],0)

    def test_wilcoxon_positive_negative_rank_sums_and_asymptotic(self):
        delays=[1.0,2.0,-3.0,-4.0]
        r=wilcoxon_delay([{
            "positive_issue_to_pr_delay_hours":str(x),
            "control_issue_to_pr_delay_hours":"0",
        } for x in delays])
        self.assertEqual(r["n"],4)
        self.assertEqual(r["positive_rank_sum"],3)
        self.assertEqual(r["negative_rank_sum"],7)
        self.assertAlmostEqual(r["effect_value"],-1)
        self.assertAlmostEqual(r["p_value"],math.erfc(
            2/math.sqrt(7.5)/math.sqrt(2)))

    def test_wilcoxon_zero_and_ties_are_handled_explicitly(self):
        delays=[0.0,1.0,-1.0,3.0]
        r=wilcoxon_delay([{
            "positive_issue_to_pr_delay_hours":str(x),
            "control_issue_to_pr_delay_hours":"0",
        } for x in delays])
        self.assertEqual(r["n"],4)
        self.assertEqual(r["nonzero"],3)
        self.assertEqual(r["tie_group_sizes"],[2])

    def test_singular_categorical_covariance_refused(self):
        with self.assertRaisesRegex(PairedReplayError,"Singular"):
            solve([[0.0]],[1.0])

    def test_original_98k_source_size_checked_before_parsing(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"C6_MATCHED_PAIR_MASTER_190.csv"
            path.write_bytes(b"index,pair_index\n")
            with self.assertRaisesRegex(PairedReplayError,"source-size"):
                audit_original(path)

    def test_symlinked_staged_original_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            f=root/"raw"
            f.write_bytes(b"CSV")
            link=root/"C6_MASTER.csv"
            link.symlink_to(f)
            with self.assertRaisesRegex(PairedReplayError,"ordinary"):
                audit_original(link)


if __name__ == "__main__":
    unittest.main()
