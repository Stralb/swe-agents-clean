"""Pure tests for changed-line counts and arm-level scope comparisons."""
import unittest
from tools.owp14_patch_scope import diff_stats, summary, TEST_PATH


class PatchScopeTests(unittest.TestCase):
    def test_add_remove_and_file_headers(self):
        patch = ("diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1,2 @@\n-old\n+one\n+two\n").encode()
        self.assertEqual(diff_stats(patch), (2,1,1))

    def test_no_git_header_is_rejected(self):
        with self.assertRaises(ValueError):diff_stats(b"+only a stray addition\n")

    def test_test_paths_are_heuristic(self):
        self.assertTrue(TEST_PATH.search('src/__tests__/a.ts'))
        self.assertTrue(TEST_PATH.search('src/a.test.ts'))
        self.assertFalse(TEST_PATH.search('src/testimonials/a.ts'))

    def test_12_case_paired_scope_counter(self):
        rows=[]
        for n in range(12):
            for arm,bs,ln in [('O',900,150),('W',600,90),('P',700,100)]:
                rows.append({'case':f'{n:05d}','arm':arm,'patch_bytes':bs,'changed_lines':ln,'changed_paths':1,'changed_tests':0})
        result=summary(rows)
        self.assertEqual(result['paired_case_count'],12)
        self.assertEqual(result['comparisons']['W_relative_to_O']['patch_bytes']['smaller'],12)
        self.assertEqual(result['arm_counts']['O']['paired_median_changed_lines'],150)

    def test_partial_cohorts_do_not_pass_three_arm_gate(self):
        with self.assertRaises(ValueError):
            summary([{'case':'00001','arm':'W','patch_bytes':20,'changed_lines':2,'changed_paths':1,'changed_tests':0}])


if __name__ == '__main__':unittest.main()
