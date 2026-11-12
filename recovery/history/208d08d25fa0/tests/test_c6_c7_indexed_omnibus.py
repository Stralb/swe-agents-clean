"""Synthetic and indexed-aggregate regression tests, never private case-level sources."""
from __future__ import annotations
import contextlib
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from analysis.c6_c7_indexed_omnibus import (
    AggregateReplayError, chi2_survival, main, replay_indexed,
    staged_c6_checks, staged_c7_strata_checks, stuart_maxwell, _load,
)

EXPECTED = {
    "Issue purpose": (9.31354906196363, 5, 0.097192565708975),
    "Instruction specificity": (15.122913505311082, 2, 0.00052011700990405),
    "Goal alignment": (16.22707423580785, 3, 0.00101867437927194),
    "Implementation category": (10.12406705406966, 6, 0.1195235832394015),
    "Primary agent/tool": (7.0219807606041, 5, 0.219010697432426),
}


def generate_synthetic_c6_source(source):
    """C6-like fixture with known original aggregates, not a copy of source CSV."""
    f = io.StringIO(newline="")
    wr = csv.writer(f)
    wr.writerow(["index", "scope", "variable", "positive_category", "control_category", "count"])
    index = 0
    for name, value in source["primary_categorical"].items():
        cats = value["categories"]
        for i, left in enumerate(cats):
            for j, right in enumerate(cats):
                count = value["counts"][i][j]
                if count:
                    wr.writerow([index, "PRIMARY", name, left, right, count]); index += 1
    while index < 165:
        wr.writerow([index, "SECONDARY", "synthetic-extra", "one", "one", 0]); index += 1
    return f.getvalue().encode()


def generate_synthetic_c7_strata(source):
    f = io.StringIO(newline="")
    w = csv.writer(f)
    w.writerow(["index", "scope", "positive_pathway", "pairs", "metric",
                "positive_rate", "matched_control_rate", "paired_difference"])
    index = 0
    for scope, pathways in source["c7_pathways"].items():
        for group, entry in pathways.items():
            for metric in ("Explicit instruction rate", "Suggests-solution rate", "Aligned goal rate"):
                p, c = entry[metric]
                n = entry["n"]
                w.writerow([index, scope, group, n, metric, repr(p/n), repr(c/n), repr((p-c)/n)])
                index += 1
    return f.getvalue().encode()


class MathTests(unittest.TestCase):
    def test_chi_square_two_degree_known_survival(self):
        self.assertAlmostEqual(chi2_survival(5.991464547107979, 2), 0.05, places=12)

    def test_chi_square_one_degree_known_survival(self):
        self.assertAlmostEqual(chi2_survival(3.841458820694124, 1), 0.05, places=12)

    def test_chi_square_three_degree_known_survival(self):
        self.assertAlmostEqual(chi2_survival(7.814727903251179, 3), 0.05, places=12)

    def test_chi_square_tails(self):
        self.assertEqual(chi2_survival(0, 6), 1.0)
        self.assertAlmostEqual(chi2_survival(10, 2), 0.006737946999085467, places=14)
        self.assertGreater(chi2_survival(10, 1), 0)
        self.assertLess(chi2_survival(100, 1), 1e-20)

    def test_two_category_equivalent_mcnemar_without_correction(self):
        x = stuart_maxwell([[12, 18], [8, 22]])
        self.assertEqual(x["n_pairs_from_contingency"], 60)
        self.assertAlmostEqual(x["chi_square"], 100/26, places=12)
        self.assertEqual(x["df"], 1)

    def test_singular_contradictory_categories_refused(self):
        with self.assertRaisesRegex(AggregateReplayError, "Singular"):
            stuart_maxwell([[20, 0, 0], [0, 10, 0], [0, 0, 10]])

    def test_zero_sample_refused(self):
        with self.assertRaises(AggregateReplayError):
            stuart_maxwell([[0, 0], [0, 0]])

    def test_negative_or_fractional_refused(self):
        for matrix in ([[1, -1], [2, 3]], [[1, .5], [2, 3]], [[1, 2, 3], [4, 5]]):
            with self.subTest(matrix=matrix), self.assertRaises(AggregateReplayError):
                stuart_maxwell(matrix)


class ResearchAggregateTests(unittest.TestCase):
    def test_all_five_primary_categorical_statistics_reproduced(self):
        value = replay_indexed()["categorical_omnibus"]
        self.assertEqual(set(value), set(EXPECTED))
        for name, (stat, df, p) in EXPECTED.items():
            with self.subTest(name=name):
                self.assertEqual(value[name]["df"], df)
                self.assertEqual(value[name]["n_pairs_from_contingency"], 190)
                self.assertAlmostEqual(value[name]["chi_square"], stat, places=9)
                self.assertAlmostEqual(value[name]["p_value"], p, places=12)

    def test_source_label_caveats_retained(self):
        s = _load()
        self.assertFalse(s["scientific_limits"]["staged_original_C6_C7_csv_sha256_verified"])
        x = replay_indexed()
        self.assertFalse(x["original_C6_C7_file_bytes_authenticated"])
        self.assertFalse(x["remaining_four_frozen_primary_tests_recomputed"])
        self.assertFalse(x["repository_blocked_resampling_reproduced"])
        self.assertFalse(x["causal_inference_supported"])

    def test_c6_marginal_190_pair_roster(self):
        result = replay_indexed()["categorical_omnibus"]
        self.assertEqual(result["Instruction specificity"]["row_totals"], [121, 36, 33])
        self.assertEqual(result["Instruction specificity"]["column_totals"], [148, 33, 9])
        self.assertEqual(result["Goal alignment"]["row_totals"], [160, 9, 19, 2])
        self.assertEqual(result["Goal alignment"]["column_totals"], [183, 3, 4, 0])

    def test_c7_pathway_partition_and_c6_marginal_agreement(self):
        result = replay_indexed()
        c7 = result["c7_pathway_margins"]
        self.assertEqual(c7["All matched pairs"]["n_pairs"], 190)
        self.assertEqual(c7["Tier-A same-repository"]["n_pairs"], 115)
        expected_counts = {
            "Explicit instruction rate": (121,148,77,95),
            "Suggests-solution rate": (33,9,15,3),
            "Aligned goal rate": (160,183,103,112),
        }
        for key, (ap,ac,tp,tc) in expected_counts.items():
            with self.subTest(metric=key):
                self.assertEqual(c7["All matched pairs"]["metrics"][key]["positive_count"], ap)
                self.assertEqual(c7["All matched pairs"]["metrics"][key]["control_count"], ac)
                self.assertEqual(c7["Tier-A same-repository"]["metrics"][key]["positive_count"], tp)
                self.assertEqual(c7["Tier-A same-repository"]["metrics"][key]["control_count"], tc)

    def test_source_pvalue_tampering_refused(self):
        data = copy.deepcopy(_load())
        data["primary_categorical"]["Issue purpose"]["historical_display_p"] = 0.002
        with self.assertRaisesRegex(AggregateReplayError, "displayed p-value"):
            replay_indexed(data)

    def test_source_cell_tampering_refused(self):
        data = copy.deepcopy(_load())
        data["primary_categorical"]["Goal alignment"]["counts"][0][0] += 1
        with self.assertRaisesRegex(AggregateReplayError, "denominator"):
            replay_indexed(data)

    def test_c7_cross_table_drift_refused(self):
        data = copy.deepcopy(_load())
        data["c7_pathways"]["All matched pairs"]["Direct-only"]["Explicit instruction rate"][0] += 1
        with self.assertRaisesRegex(AggregateReplayError, "margins"):
            replay_indexed(data)

    def test_invalid_c7_subgroup_refused(self):
        data = copy.deepcopy(_load())
        data["c7_pathways"]["Tier-A same-repository"]["Direct-only"]["n"] = 60
        with self.assertRaisesRegex(AggregateReplayError, "denominator"):
            replay_indexed(data)

    def test_indexed_cli_succeeds_and_preserves_scope(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["replay-indexed"])
        self.assertEqual(code, 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["primary_categorical_tests_recomputed"], 5)
        self.assertFalse(data["original_C6_C7_file_bytes_authenticated"])


class StagedSourceVerificationTests(unittest.TestCase):
    def test_staged_fixture_can_reconcile_after_explicit_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c6_source(source)
            path = Path(directory) / "synthetic-c6.csv"
            path.write_bytes(raw)
            result = staged_c6_checks(path, hashlib.sha256(raw).hexdigest(), source,
                                      source_bytes=len(raw))
            self.assertTrue(result["original_C6_contingency_source_sha256_verified"])
            self.assertFalse(result["original_C6_C7_file_bytes_authenticated"])

    def test_staged_file_requires_authenticated_preexisting_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c6_source(source)
            path = Path(directory) / "sample.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(AggregateReplayError, "digest"):
                staged_c6_checks(path, "f"*64, source, source_bytes=len(raw))

    def test_staged_rejects_tampered_counts_even_with_matching_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c6_source(source)
            raw = raw.replace(b"Explicit instruction,Explicit instruction,98",
                              b"Explicit instruction,Explicit instruction,97")
            path = Path(directory) / "synthetic-changed.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(AggregateReplayError, "disagrees"):
                staged_c6_checks(path, hashlib.sha256(raw).hexdigest(), source,
                                 source_bytes=len(raw))

    def test_staged_symlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c6_source(source)
            path = Path(directory) / "synthetic-c6.csv"
            path.write_bytes(raw)
            link = Path(directory) / "symlink.csv"
            link.symlink_to(path)
            with self.assertRaisesRegex(AggregateReplayError, "Symlink"):
                staged_c6_checks(link, hashlib.sha256(raw).hexdigest(), source,
                                 source_bytes=len(raw))

    def test_staged_c7_strata_source_can_match_indexed_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c7_strata(source)
            path = Path(directory) / "synthetic-c7-strata.csv"
            path.write_bytes(raw)
            answer = staged_c7_strata_checks(path, hashlib.sha256(raw).hexdigest(),
                                             source, source_bytes=len(raw))
            self.assertTrue(answer["staged_C7_strata_source_sha256_matched_supplied_digest"])
            self.assertFalse(answer["original_C7_pair_level_pathways_authenticated"])

    def test_staged_c7_strata_drift_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c7_strata(source)
            raw = raw.replace(b"0.6153846153846154", b"0.7153846153846154", 1)
            path = Path(directory)/"modified-c7.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(AggregateReplayError, "C7 source rates"):
                staged_c7_strata_checks(path, hashlib.sha256(raw).hexdigest(),
                                        source, source_bytes=len(raw))

    def test_staged_c7_missing_row_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c7_strata(source)
            raw = b"\n".join(raw.split(b"\n")[:-2]) + b"\n"
            path = Path(directory)/"missing-c7.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(AggregateReplayError, "row count"):
                staged_c7_strata_checks(path, hashlib.sha256(raw).hexdigest(),
                                        source, source_bytes=len(raw))

    def test_staged_c7_requires_preestablished_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            source = _load()
            raw = generate_synthetic_c7_strata(source)
            path = Path(directory)/"synthetic-c7.csv"
            path.write_bytes(raw)
            with self.assertRaisesRegex(AggregateReplayError, "digest"):
                staged_c7_strata_checks(path, "a"*64, source, source_bytes=len(raw))

    def test_cli_refuses_unpinned_frozen_original(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)/"fake.csv"
            p.write_text("abc", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["verify-staged-c6", str(p), "0"*64])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(out.getvalue())["original_source_statistically_reproduced"])


if __name__ == "__main__":
    unittest.main()
