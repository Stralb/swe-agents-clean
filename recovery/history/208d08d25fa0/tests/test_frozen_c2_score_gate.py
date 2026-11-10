"""Synthetic-only tests for source-pinned C2 arithmetic and grouping."""
from __future__ import annotations

import contextlib
import copy
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

from analysis.frozen_c2_score_gate import (
    C2ScoreError, FINGERPRINTS, _quantile, main, verify_scores,
)

PAIR_FIELDS = [
    "positive_case_id", "control_case_id", "match_tier", "same_repository",
    "positive_repository", "control_repository", "opportunity_relation",
    "positive_opportunity_signature", "control_opportunity_signature",
    "positive_pr_created_at", "control_pr_created_at", "abs_pr_time_days",
    "positive_changed_lines", "control_changed_lines",
    "abs_log1p_changed_lines_diff", "changed_lines_ratio_larger_to_smaller_approx",
    "positive_changed_files", "control_changed_files",
    "abs_log1p_changed_files_diff", "changed_files_ratio_larger_to_smaller_approx",
    "normalized_distance",
]


def pair(pos, control, tier, pr, cr, ps, cs, pdate="2026-01-01T00:00:00Z",
         cdate="2026-01-04T00:00:00Z", pl=10, cl=20, pf=1, cf=2):
    days = abs((datetime.fromisoformat(pdate.replace("Z", "+00:00"))-
                datetime.fromisoformat(cdate.replace("Z", "+00:00"))).total_seconds())/86400
    dlines = abs(math.log1p(pl)-math.log1p(cl))
    dfiles = abs(math.log1p(pf)-math.log1p(cf))
    rl = (max(pl, cl)+1)/(min(pl, cl)+1)
    rf = (max(pf, cf)+1)/(min(pf, cf)+1)
    return dict(zip(PAIR_FIELDS, map(str, [pos, control, tier,
        int(pr==cr), pr, cr, "exact" if ps==cs else "superset", ps, cs,
        pdate, cdate, days, pl, cl, dlines, rl, pf, cf, dfiles, rf,
        days/90 + (dlines+dfiles)/math.log(4)])))


def rows():
    return [pair(11, 21, "A", "syn/a", "syn/a", "codeql", "codeql"),
            pair(12, 22, "A", "syn/b", "syn/b", "codeql", "codeql;gitleaks",
                 pl=30, cl=25, pf=4, cf=3),
            pair(13, 23, "B", "syn/c", "syn/d", "semgrep", "semgrep",
                 pl=4, cl=7, pf=2, cf=1)]


def write_csv(path, headers, data):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(data)


def make_fixture(dirpath, data=None):
    data = copy.deepcopy(data or rows())
    paths = {name: dirpath / (name + ".csv") for name in
             ("pairs", "balance", "quality")}
    paths["summary"] = dirpath / "summary.json"
    write_csv(paths["pairs"], PAIR_FIELDS, data)
    vals = {"absolute_pr_time_days": [float(x["abs_pr_time_days"]) for x in data],
            "changed_lines_ratio_larger_to_smaller_approx": [float(x["changed_lines_ratio_larger_to_smaller_approx"]) for x in data],
            "changed_files_ratio_larger_to_smaller_approx": [float(x["changed_files_ratio_larger_to_smaller_approx"]) for x in data],
            "normalized_distance": [float(x["normalized_distance"]) for x in data]}
    balance = [{"metric": k, "median": _quantile(v, .5),
                "p90": _quantile(v, .9), "max": max(v)} for k, v in vals.items()]
    write_csv(paths["balance"], ["metric", "median", "p90", "max"], balance)
    grouped = {}
    for row in data:
        grouped.setdefault((row["match_tier"], row["opportunity_relation"]), []).append(row)
    quality = []
    for (tier, relation), matches in sorted(grouped.items()):
        groups = [("median_time_days", "abs_pr_time_days"),
                  ("median_line_ratio", "changed_lines_ratio_larger_to_smaller_approx"),
                  ("median_file_ratio", "changed_files_ratio_larger_to_smaller_approx"),
                  ("median_distance", "normalized_distance")]
        record = {"match_tier": tier, "opportunity_relation": relation,
                  "pairs": len(matches)}
        for label, key in groups:
            record[label] = _quantile([float(x[key]) for x in matches], .5)
        quality.append(record)
    write_csv(paths["quality"], ["match_tier", "opportunity_relation", "pairs",
        "median_time_days", "median_line_ratio", "median_file_ratio", "median_distance"], quality)
    summary = {
        "c1_input_sha256": "f"*64, "matched_pairs": len(data),
        "tier_a_same_repo_pairs": sum(x["match_tier"]=="A" for x in data),
        "tier_b_cross_repo_exact_pairs": sum(x["match_tier"]=="B" for x in data),
        "time_caliper_days": 90.0, "size_ratio_caliper_approx": 4.0,
        "median_abs_time_days": _quantile(vals["absolute_pr_time_days"], .5),
        "p90_abs_time_days": _quantile(vals["absolute_pr_time_days"], .9),
        "median_changed_lines_ratio": _quantile(vals["changed_lines_ratio_larger_to_smaller_approx"], .5),
        "p90_changed_lines_ratio": _quantile(vals["changed_lines_ratio_larger_to_smaller_approx"], .9),
        "median_changed_files_ratio": _quantile(vals["changed_files_ratio_larger_to_smaller_approx"], .5),
        "p90_changed_files_ratio": _quantile(vals["changed_files_ratio_larger_to_smaller_approx"], .9),
        "same_repository_fraction": sum(x["match_tier"]=="A" for x in data)/len(data),
    }
    paths["summary"].write_text(json.dumps(summary), encoding="utf-8")
    pins = {k: (p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())
            for k, p in paths.items()}
    return paths, pins


def verify(paths, pins):
    return verify_scores(paths["pairs"], paths["summary"],
                         paths["balance"], paths["quality"],
                         pins=pins, expected_pairs=3, expected_a=2,
                         expected_c1_sha="f"*64)


def renew(pins, path, role):
    pins[role] = (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())


def rewrite_csv(path, change):
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        headers, rows = list(reader.fieldnames), list(reader)
    change(rows)
    write_csv(path, headers, rows)


class FrozenC2SelectedPairScoreTests(unittest.TestCase):
    def test_frozen_sha256_pins_not_fake(self):
        self.assertEqual(FINGERPRINTS["pairs"][1],
            "4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b")
        self.assertEqual(FINGERPRINTS["summary"][0], 1025)

    def test_scores_and_subgroup_distributions_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            before = {k: v.read_bytes() for k, v in paths.items()}
            got = verify(paths, pins)
            self.assertEqual(got["verified_pair_rows"], 3)
            self.assertEqual(got["opportunity_group_counts"],
                             {"A_exact": 1, "A_superset": 1, "B_exact": 1})
            self.assertFalse(got["original_global_matching_optimizer_rerun"])
            self.assertEqual(before, {k: v.read_bytes() for k, v in paths.items()})

    def test_original_file_digest_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            paths["pairs"].write_bytes(paths["pairs"].read_bytes()+b"x")
            with self.assertRaisesRegex(C2ScoreError, "size"):
                verify(paths, pins)

    def test_wrong_distance_even_with_refreshed_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[0].update({"normalized_distance": "0.1"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "normalized_distance"):
                verify(paths, pins)

    def test_wrong_changed_lines_ratio_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[0].update({
                "changed_lines_ratio_larger_to_smaller_approx": "2.5"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "changed_lines_ratio"):
                verify(paths, pins)

    def test_wrong_tier_relation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[1].update({
                "opportunity_relation": "exact"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "opportunity relation"):
                verify(paths, pins)

    def test_opportunity_superset_is_not_cross_repository_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[1].update({
                "match_tier": "B", "positive_repository": "syn/other",
                "same_repository": "0"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "Invalid Tier B"):
                verify(paths, pins)

    def test_90_day_caliper_violation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[0].update({
                "control_pr_created_at": "2026-09-01T00:00:00Z"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "caliper"):
                verify(paths, pins)

    def test_4x_changed_lines_caliper_violation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[0].update({
                "control_changed_lines": "999"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "caliper"):
                verify(paths, pins)

    def test_nonfinite_metric_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[0].update({
                "normalized_distance": "NaN"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "Non-finite"):
                verify(paths, pins)

    def test_wrong_balance_with_refreshed_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["balance"], lambda rs: rs[0].update({"p90": "9876"}))
            renew(pins, paths["balance"], "balance")
            with self.assertRaisesRegex(C2ScoreError, "balance"):
                verify(paths, pins)

    def test_wrong_tier_quality_with_refreshed_hash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["quality"], lambda rs: rs[0].update({"median_distance": "9876"}))
            renew(pins, paths["quality"], "quality")
            with self.assertRaisesRegex(C2ScoreError, "quality"):
                verify(paths, pins)

    def test_corrupt_summary_even_after_rehash_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            original = json.loads(paths["summary"].read_text())
            original["median_abs_time_days"] = 9876
            paths["summary"].write_text(json.dumps(original))
            renew(pins, paths["summary"], "summary")
            with self.assertRaisesRegex(C2ScoreError, "summary median_abs_time_days"):
                verify(paths, pins)

    def test_unsafe_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            alias = Path(tmp) / "alias.csv"
            alias.symlink_to(paths["pairs"])
            paths["pairs"] = alias
            with self.assertRaisesRegex(C2ScoreError, "symlink"):
                verify(paths, pins)

    def test_empty_or_duplicate_opportunity_token_rejected(self):
        for bad in ("codeql;codeql", "codeql;", ""):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                paths, pins = make_fixture(Path(tmp))
                rewrite_csv(paths["pairs"], lambda rs: rs[0].update({
                    "positive_opportunity_signature": bad}))
                renew(pins, paths["pairs"], "pairs")
                with self.assertRaisesRegex(C2ScoreError, "signature"):
                    verify(paths, pins)

    def test_duplicate_positive_case_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            rewrite_csv(paths["pairs"], lambda rs: rs[1].update({
                "positive_case_id": "11"}))
            renew(pins, paths["pairs"], "pairs")
            with self.assertRaisesRegex(C2ScoreError, "Duplicate"):
                verify(paths, pins)

    def test_public_cli_rejects_synthetic_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main([str(paths[k]) for k in ("pairs", "summary", "balance", "quality")])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(out.getvalue())["scientific_replication_complete"])



class FrozenC2CandidateCertificateTests(unittest.TestCase):
    """Small synthetic candidate counts; never use Wits originals in CI."""

    def _setup(self, tmp):
        paths, pins = make_fixture(Path(tmp))
        candidate = Path(tmp) / "candidate_counts.csv"
        records = [
            {"positive_case_id": "11", "repository": "syn/a",
             "required_complete_opportunity_signature": "codeql",
             "tier_a_same_repo_candidates": "2", "tier_b_cross_repo_exact_candidates": "0",
             "has_any_eligible_candidate": "1"},
            {"positive_case_id": "12", "repository": "syn/b",
             "required_complete_opportunity_signature": "codeql",
             "tier_a_same_repo_candidates": "1", "tier_b_cross_repo_exact_candidates": "0",
             "has_any_eligible_candidate": "1"},
            {"positive_case_id": "13", "repository": "syn/c",
             "required_complete_opportunity_signature": "semgrep",
             "tier_a_same_repo_candidates": "0", "tier_b_cross_repo_exact_candidates": "5",
             "has_any_eligible_candidate": "1"},
            {"positive_case_id": "14", "repository": "syn/d",
             "required_complete_opportunity_signature": "codeql",
             "tier_a_same_repo_candidates": "0", "tier_b_cross_repo_exact_candidates": "0",
             "has_any_eligible_candidate": "0"},
        ]
        write_csv(candidate, ["positive_case_id", "repository",
            "required_complete_opportunity_signature", "tier_a_same_repo_candidates",
            "tier_b_cross_repo_exact_candidates", "has_any_eligible_candidate"], records)
        return paths, pins, candidate

    def _verify(self, paths, pins, candidate):
        from analysis.frozen_c2_score_gate import verify_candidate_cardinality
        return verify_candidate_cardinality(candidate, paths["pairs"],
            candidate_pin=(candidate.stat().st_size,
                           hashlib.sha256(candidate.read_bytes()).hexdigest()),
            pairs_pin=pins["pairs"], expected_positive_cases=4,
            expected_pairs=3, expected_tier_a=2, expected_unmatched=("14",))

    def test_cardinality_certificate_from_frozen_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            report = self._verify(paths, pins, candidate)
            self.assertTrue(report["maximum_cardinality_proven_given_frozen_counts"])
            self.assertEqual(report["source_recorded_tier_a_candidate_edges"], 3)
            self.assertEqual(report["source_recorded_tier_b_candidate_edges"], 5)
            self.assertFalse(report["tier_a_optimality_reproduced"])

    def test_unmatched_positive_with_eligible_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            rewrite_csv(candidate, lambda rows: rows[-1].update({
                "tier_b_cross_repo_exact_candidates": "1",
                "has_any_eligible_candidate": "1"}))
            with self.assertRaisesRegex(C2ScoreError, "maximum-cardinality"):
                self._verify(paths, pins, candidate)

    def test_chosen_tier_without_eligible_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            rewrite_csv(candidate, lambda rows: rows[0].update({
                "tier_a_same_repo_candidates": "0",
                "tier_b_cross_repo_exact_candidates": "1"}))
            with self.assertRaisesRegex(C2ScoreError, "tier has zero"):
                self._verify(paths, pins, candidate)

    def test_candidate_flag_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            rewrite_csv(candidate, lambda rows: rows[0].update({
                "has_any_eligible_candidate": "0"}))
            with self.assertRaisesRegex(C2ScoreError, "eligibility flag"):
                self._verify(paths, pins, candidate)

    def test_candidate_repository_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            rewrite_csv(candidate, lambda rows: rows[0].update({
                "repository": "syn/other"}))
            with self.assertRaisesRegex(C2ScoreError, "differs from original"):
                self._verify(paths, pins, candidate)

    def test_duplicate_candidate_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            rewrite_csv(candidate, lambda rows: rows[-1].update({
                "positive_case_id": "11"}))
            with self.assertRaisesRegex(C2ScoreError, "Duplicate"):
                self._verify(paths, pins, candidate)

    def test_changed_candidate_bytes_fail_pinned_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins, candidate = self._setup(tmp)
            from analysis.frozen_c2_score_gate import verify_candidate_cardinality
            original_pin = (candidate.stat().st_size,
                            hashlib.sha256(candidate.read_bytes()).hexdigest())
            candidate.write_bytes(candidate.read_bytes().replace(b"syn/a", b"syn/x"))
            with self.assertRaisesRegex(C2ScoreError, "SHA-256"):
                verify_candidate_cardinality(candidate, paths["pairs"],
                    candidate_pin=original_pin, pairs_pin=pins["pairs"],
                    expected_positive_cases=4, expected_pairs=3,
                    expected_tier_a=2, expected_unmatched=("14",))


if __name__ == "__main__":
    unittest.main()

class FrozenCandidateCommandTests(unittest.TestCase):
    def test_cli_rejects_nonfrozen_synthetic_inputs_without_override(self):
        from analysis.frozen_c2_candidate_cardinality import main
        with tempfile.TemporaryDirectory() as tmp:
            paths, pins = make_fixture(Path(tmp))
            candidate = Path(tmp) / 'candidate.csv'
            candidate.write_text('positive_case_id,repository\n1,syn/a\n')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main([str(candidate), str(paths['pairs'])])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads(output.getvalue())[
                'original_candidate_generator_reproduced'])
