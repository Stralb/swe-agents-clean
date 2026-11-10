"""Only aggregate/read-only source-ledger checks. Never touches Wits or issues."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest

from analysis.late_issue_root_scope_gate import (
    LateIssueScopeError, SOURCE, D7_DIFF, inspect, main,
)


def fixtures():
    return {
        "ledger": json.loads(SOURCE.read_text(encoding="utf-8")),
        "differences_csv": D7_DIFF.read_text(encoding="utf-8"),
    }


class LateIssueRootScopeTests(unittest.TestCase):
    def test_original_four_case_root_and_disagreement_counts(self):
        out = inspect()
        self.assertEqual(out["frozen_census_root_count"], 342)
        self.assertEqual(out["frozen_disputed_root_count"], 43)
        self.assertEqual(out["late_issue_positive_case_count"], 4)
        self.assertEqual(out["late_issue_positive_root_count"], 14)
        self.assertEqual(out["late_issue_positive_conflicting_roots"], 8)
        self.assertEqual(out["remaining_other_roots"], 328)
        self.assertEqual(out["remaining_other_conflicting_roots"], 35)
        self.assertEqual(out["different_PR_workstream_root_count"], 12)
        self.assertEqual(out["different_PR_workstream_conflicting_roots"], 7)

    def test_expected_disagreements_per_case(self):
        got = {x["case_id"]: x["conflicting_root_count"] for x in inspect()["case_rows"]}
        self.assertEqual(got, {5264: 3, 5267: 4, 7682: 0, 12334: 1})

    def test_sources_never_claim_causal_inference_or_original_master(self):
        out = inspect()
        self.assertFalse(out["root_level_causal_issue_influence_proven"])
        self.assertFalse(out["historical_issue_asof_PR_content_verified"])
        self.assertFalse(out["original_final_SQLite_authenticated"])
        self.assertFalse(out["original_C6_pairwise_coding_recovered"])
        self.assertTrue(out["candidate_sqlite_and_public_current_snapshots_only"])

    def test_issue_created_before_PR_is_rejected(self):
        x = fixtures()
        item = x["ledger"]["reviewed_issue_after_pr_positive_cases"][0]
        item["issue_created_utc"] = "2026-06-05T08:35:11Z"
        with self.assertRaisesRegex(LateIssueScopeError, "Issue not strictly"):
            inspect(**x)

    def test_mistaken_root_workflow_id_is_rejected(self):
        x = fixtures()
        item = x["ledger"]["reviewed_issue_after_pr_positive_cases"][0]
        item["root_ids"][0] = "CROOT-05267-01"
        with self.assertRaisesRegex(LateIssueScopeError, "root membership"):
            inspect(**x)

    def test_duplicate_root_rejected(self):
        x = fixtures()
        item = x["ledger"]["reviewed_issue_after_pr_positive_cases"][0]
        item["root_ids"][1] = item["root_ids"][0]
        with self.assertRaisesRegex(LateIssueScopeError, "root membership"):
            inspect(**x)

    def test_outcome_relabel_or_falsely_adjudicated_label_is_rejected(self):
        x = fixtures()
        x["differences_csv"] = x["differences_csv"].replace(",UNRESOLVED,", ",ADJUDICATED,", 1)
        with self.assertRaisesRegex(LateIssueScopeError, "adjudicated"):
            inspect(**x)

    def test_tampered_conflict_root_is_rejected(self):
        x = fixtures()
        x["differences_csv"] = x["differences_csv"].replace("CROOT-05267-01", "CROOT-05267-99", 1)
        with self.assertRaisesRegex(LateIssueScopeError, "intersection changed"):
            inspect(**x)

    def test_false_causal_source_provenance_rejected(self):
        x = fixtures()
        x["ledger"]["interpretation_limits"]["scope_labels_are_adjudicated"] = True
        with self.assertRaisesRegex(LateIssueScopeError, "adjudication"):
            inspect(**x)

    def test_false_final_database_authentication_rejected(self):
        x = fixtures()
        x["ledger"]["source_provenance"]["final_frozen_sqlite_sha256_authenticated"] = True
        with self.assertRaisesRegex(LateIssueScopeError, "source"):
            inspect(**x)

    def test_fix_commit_before_linked_issue_rejected(self):
        x = fixtures()
        x["ledger"]["reviewed_issue_after_pr_positive_cases"][1]["issue_specific_fix_commit_utc"] = (
            "2026-05-28T04:00:00Z")
        with self.assertRaisesRegex(LateIssueScopeError, "fix commit"):
            inspect(**x)

    def test_cli_json_has_no_full_issue_bodies(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main([]), 0)
        parsed = json.loads(stdout.getvalue())
        self.assertEqual(parsed["late_issue_positive_root_count"], 14)
        self.assertEqual(len(parsed["case_rows"]), 4)
        self.assertNotIn("issue_body", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
