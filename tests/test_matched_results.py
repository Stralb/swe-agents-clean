"""Regression checks for the aggregate matched-results package."""
import unittest
from checks.matched_results import DATA, exact_mcnemar, replay, stuart_maxwell

class MatchedResultsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {r["variable"]: r for r in replay(check=True)}

    def test_nine_predefined_comparisons(self):
        self.assertEqual(len(self.rows), 9)

    def test_original_significant_results_after_holm(self):
        significant = {k for k,v in self.rows.items() if v["holm_p"] < .05}
        self.assertEqual(significant, {"Instruction specificity","Goal alignment"})

    def test_specificity(self):
        x = self.rows["Instruction specificity"]
        self.assertEqual(x["pairs"],190)
        self.assertAlmostEqual(x["p_value"],.000520117009904,places=10)
        self.assertAlmostEqual(x["effect"],.1421052631578947,places=12)
        self.assertAlmostEqual(x["holm_p"],.004681053089136,places=9)

    def test_goal_alignment(self):
        x = self.rows["Goal alignment"]
        self.assertEqual(x["pairs"],190)
        self.assertAlmostEqual(x["p_value"],.0010186743792719,places=9)
        self.assertAlmostEqual(x["holm_p"],.0081493950341752,places=8)

    def test_review_excludes_one_pair_not_as_no(self):
        x = self.rows["Formal human review before merge"]
        self.assertEqual(x["pairs"],189)
        self.assertEqual((x["discordant_positive_only"],
                          x["discordant_control_only"]), (31,24))
        self.assertAlmostEqual(x["p_value"],.4187541882690154,places=14)

    def test_activity_excludes_three_pairs(self):
        x = self.rows["Any requester prior repo activity"]
        self.assertEqual(x["pairs"],187)
        self.assertEqual((x["discordant_positive_only"],
                          x["discordant_control_only"]), (30,39))
        self.assertAlmostEqual(x["p_value"],.3355576182340152,places=14)

    def test_historical_delay_is_not_falsely_replayed(self):
        x = self.rows["Issue→PR creation delay (hours)"]
        self.assertEqual(x["source"],"historical report")
        self.assertAlmostEqual(x["effect"],-.4049444444444438)

    def test_categorical_zero_difference(self):
        x=stuart_maxwell([[8,3],[3,7]])
        self.assertAlmostEqual(x["statistic"],0.)
        self.assertAlmostEqual(x["p_value"],1.)

    def test_exact_discordance(self):
        x=exact_mcnemar(dict(both_yes=23,positive_only_yes=31,
                             control_only_yes=24,both_no=111,complete_pairs=189))
        self.assertAlmostEqual(x["p_value"],.4187541882690154,places=14)

    def test_no_case_level_data_in_distributable_tables(self):
        raw=DATA.read_text(encoding="utf-8")
        self.assertNotIn("positive_case_id",raw)
        self.assertNotIn("issue_body",raw)
        self.assertNotIn("repository_url",raw)

if __name__ == "__main__":
    unittest.main()
