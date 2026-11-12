"""Synthetic and non-private indexed paired-matrix bootstrap distribution tests."""
from __future__ import annotations
import contextlib
import copy
import io
import json
import unittest
from analysis.c6_indexed_pair_bootstrap_ci import (
    IndexedBootstrapError, SOURCE, AGGREGATES, empirical_bootstrap_pmf,
    paired_difference_counts, quantile_of_signed_sum, replay, main
)


def fixtures():
    return dict(source=json.loads(SOURCE.read_text()),
                aggregates=json.loads(AGGREGATES.read_text()))


class AnalyticBootstrapTests(unittest.TestCase):
    def test_trinomial_two_draw_distribution(self):
        pmf=empirical_bootstrap_pmf(1,1,0)
        self.assertEqual(pmf,[.25,0.,.5,0.,.25])
        self.assertEqual(quantile_of_signed_sum(pmf,.025),-2)
        self.assertEqual(quantile_of_signed_sum(pmf,.975),2)

    def test_only_zero_differences(self):
        pmf=empirical_bootstrap_pmf(0,0,4)
        self.assertEqual(pmf[4],1.0)
        self.assertAlmostEqual(sum(pmf),1)
        self.assertEqual(quantile_of_signed_sum(pmf,.025),0)
        self.assertEqual(quantile_of_signed_sum(pmf,.975),0)

    def test_unbalanced_no_zero_pair_pmf(self):
        pmf=empirical_bootstrap_pmf(3,1,0)
        self.assertAlmostEqual(sum(pmf),1.,places=12)
        self.assertEqual(len(pmf),9)
        self.assertAlmostEqual(pmf[0],(1/4)**4,places=12)
        self.assertAlmostEqual(pmf[8],(3/4)**4,places=12)

    def test_invalid_signed_counts_rejected(self):
        for x in [(-1,2,3),(1,-1,3),(1,1,-1),(0,0,0),(1.5,1,2)]:
            with self.subTest(x=x),self.assertRaises(IndexedBootstrapError):
                empirical_bootstrap_pmf(*x)

    def test_invalid_quantile_rejected(self):
        pmf=empirical_bootstrap_pmf(1,1,0)
        for q in [-.01,0,1,1.01,float('nan')]:
            with self.subTest(q=q),self.assertRaises(IndexedBootstrapError):
                quantile_of_signed_sum(pmf,q)

    def test_binary_matrix_signed_pair_counts(self):
        self.assertEqual(paired_difference_counts([[8,3],[5,4]],0),(3,5,12))

    def test_non_square_or_negative_matrix_rejected(self):
        for mat in ([[1,2,3],[3,4,5]], [[1,2],[-1,4]]):
            with self.subTest(mat=mat),self.assertRaises(IndexedBootstrapError):
                paired_difference_counts(mat,0)


class C6IndexedSourceConsistencyTests(unittest.TestCase):
    def test_main_three_pair_bootstrap_ci_consistency(self):
        o=replay()
        self.assertEqual(o['categories_checked'],3)
        self.assertTrue(all(x['match_within_one_discrete_pair_increment'] for x in o['comparisons']))
        self.assertFalse(o['original_C6_source_sha256_verified'])
        self.assertFalse(o['source_ci_method_exactly_reproduced'])

    def test_explicit_instruction_difference_and_analytic_ci(self):
        o=replay()
        z=next(x for x in o['comparisons'] if x['category']=='Explicit instruction')
        self.assertEqual((z['positive_only_pairs'],z['control_only_pairs']), (23,50))
        self.assertAlmostEqual(z['observed_paired_difference_pp'],-14.210526315789473)
        self.assertAlmostEqual(z['analytic_resampling_ci95_pp'][0],-22.63157894736842)
        self.assertAlmostEqual(z['analytic_resampling_ci95_pp'][1],-5.7894736842105265)

    def test_suggests_solution_ci_one_increment_difference(self):
        z=next(x for x in replay()['comparisons'] if x['category']=='Suggests solution')
        self.assertEqual((z['positive_only_pairs'],z['control_only_pairs']), (33,9))
        self.assertAlmostEqual(z['analytic_resampling_ci95_pp'][1],18.947368421052634)
        self.assertAlmostEqual(z['source_reported_pair_bootstrap_ci95_pp'][1],19.473684210526315)

    def test_aligned_goal_ci_near_original(self):
        z=next(x for x in replay()['comparisons'] if x['category']=='Aligned')
        self.assertEqual((z['positive_only_pairs'],z['control_only_pairs']), (5,28))
        self.assertAlmostEqual(z['analytic_resampling_ci95_pp'][0],-17.894736842105264)
        self.assertAlmostEqual(z['analytic_resampling_ci95_pp'][1],-6.315789473684211)

    def test_broken_original_reported_interval_is_detected(self):
        x=fixtures()
        x['source']['source_reported_rows'][0]['source_reported_pair_boot_ci95_low_pp']=-40
        with self.assertRaisesRegex(IndexedBootstrapError,'over one'):
            replay(**x)

    def test_changed_pair_count_is_detected(self):
        x=fixtures()
        x['aggregates']['primary_categorical']['Goal alignment']['counts'][0][0] += 1
        with self.assertRaisesRegex(IndexedBootstrapError,'margin'):
            replay(**x)

    def test_missing_source_label_is_detected(self):
        x=fixtures()
        x['source']['source_reported_rows'][2]['category']='Unclear'
        with self.assertRaisesRegex(IndexedBootstrapError,'Expected three'):
            replay(**x)

    def test_false_provenance_claim_rejected(self):
        x=fixtures()
        x['source']['original_source_C6_file_bytes_authenticated']=True
        with self.assertRaisesRegex(IndexedBootstrapError,'unsupported'):
            replay(**x)

    def test_cli_reports_noncausal_scope(self):
        b=io.StringIO()
        with contextlib.redirect_stdout(b):
            status=main([])
        self.assertEqual(status,0)
        v=json.loads(b.getvalue())
        self.assertEqual(v['categories_checked'],3)
        self.assertFalse(v['causal_interpretation_supported'])


if __name__=='__main__':
    unittest.main()
