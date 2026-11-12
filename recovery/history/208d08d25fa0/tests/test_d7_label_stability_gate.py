"""Pure, source-pinned D/D7 label-stability tests without private files."""
from __future__ import annotations

import contextlib
import copy
import csv
import io
import json
import unittest

from analysis.d7_label_stability_gate import (
    D7StabilityError,
    SOURCE,
    SOURCE_GIT_BLOB_SHA1,
    audit,
    git_blob_hash,
    inspect_rows,
    main,
)


def source_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(SOURCE.read_text(encoding="utf-8"))))


class D7LabelStabilityTests(unittest.TestCase):
    def test_unmodified_source_has_exact_recorded_git_blob_hash(self):
        self.assertEqual(git_blob_hash(SOURCE.read_bytes()),
                         SOURCE_GIT_BLOB_SHA1)

    def test_source_counts_and_route_stability(self):
        result = audit()
        self.assertEqual(result["unresolved_root_disagreements"], 43)
        self.assertEqual(result["distinct_workflows_with_disagreements"], 34)
        self.assertEqual(result["route_changed"], 1)
        self.assertEqual(result["tier_changed_with_route_stable"], 42)
        self.assertEqual(result["top_level_route_agreement_count"], 341)
        self.assertEqual(result["full_route_tier_exact_agreement_count"], 299)
        self.assertEqual(result["common_M_tier_agreement_count"], 191)
        self.assertEqual(result["common_M_tier_agreement_denominator"], 233)

    def test_incomplete_status_and_workflow_subgroup_counts(self):
        result = audit()
        self.assertEqual(result["incomplete_status_disputes"], 17)
        self.assertEqual(result["completed_tier_only_disputes"], 25)
        self.assertEqual(result["incomplete_dispute_workflows"], 10)
        self.assertEqual(result["completed_tier_dispute_workflows"], 24)

    def test_tier_differences_from_frozen_ledger(self):
        result = audit()
        deltas = {x["label"]: x["d7_minus_d_final"]
                  for x in result["disputed_label_version_counts"]}
        self.assertEqual(deltas, {
            "H/NA": 1, "M/INCOMPLETE": 7, "M/T1": -13,
            "M/T2": 1, "M/T3": 5, "M/T4": 3, "M/T5": -4,
        })
        self.assertEqual(sum(deltas.values()), 0)
        t1 = [x for x in result["disputed_label_version_counts"]
              if x["label"] == "M/T1"][0]
        self.assertEqual((t1["d_final_disputed_count"],
                          t1["d7_disputed_count"]), (16, 3))
        self.assertEqual(t1["possible_if_select_either_recorded_label"], 19)

    def test_source_route_totals_not_artificially_independent(self):
        result = audit()
        self.assertEqual(result["source_reported_D_final_route_totals"],
                         {"H": 5, "T": 103, "M": 234})
        self.assertEqual(result["source_reported_D7_route_totals"],
                         {"H": 6, "T": 103, "M": 233})
        self.assertFalse(result["scientific_nonclaims"]
                         ["original_D_and_D7_full_raw_342_root_files_authenticated"])
        self.assertFalse(result["scientific_nonclaims"]
                         ["inter_rater_reliability_estimated"])
        self.assertFalse(result["scientific_nonclaims"]
                         ["source_difference_table_independently_adjudicated"])

    def test_changed_source_bytes_are_rejected_before_interpretation(self):
        with self.assertRaisesRegex(D7StabilityError, "Git blob SHA"):
            audit(SOURCE.read_bytes() + b"# untrusted update")

    def test_duplicate_root_rejected(self):
        rows = source_rows()
        rows[-1]["root_id"] = rows[0]["root_id"]
        with self.assertRaisesRegex(D7StabilityError, "Duplicate"):
            inspect_rows(rows)

    def test_silent_adjudication_rejected(self):
        rows = source_rows()
        rows[0]["disposition"] = "ACCEPT_D7"
        with self.assertRaisesRegex(D7StabilityError, "silently adjudicated"):
            inspect_rows(rows)

    def test_false_disagreement_rejected(self):
        rows = source_rows()
        rows[0]["d7_route"] = rows[0]["d_final_route"]
        rows[0]["d7_tier"] = rows[0]["d_final_tier"]
        with self.assertRaisesRegex(D7StabilityError, "Unchanged root"):
            inspect_rows(rows)

    def test_unexpected_second_route_change_rejected(self):
        rows = source_rows()
        rows[0]["d7_route"] = "H"
        rows[0]["d7_tier"] = "NA"
        with self.assertRaisesRegex(D7StabilityError, "Unexpected route"):
            inspect_rows(rows)

    def test_incorrect_incomplete_count_rejected(self):
        rows = source_rows()
        rows[0]["d7_tier"] = "T2"
        with self.assertRaisesRegex(D7StabilityError, "category counts"):
            inspect_rows(rows)

    def test_cli_emits_aggregate_json_only(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(main(), 0)
        obj = json.loads(buf.getvalue())
        self.assertEqual(obj["status"],
                         "PASS_D_FINAL_D7_LEDGER_ONLY_CATEGORICAL_STABILITY")
        self.assertEqual(obj["route_changed"], 1)
        self.assertNotIn("CROOT-00649-01", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
