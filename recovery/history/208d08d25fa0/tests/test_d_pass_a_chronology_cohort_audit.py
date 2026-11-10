"""Synthetic-only tests: running CI does not replay original 25 MB Wits Pass-A."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from analysis.d_pass_a_chronology_cohort_audit import (
    CASE154_ROOT,
    ORIGINAL_SIZE,
    ORIGINAL_SHA256,
    OriginalChronologyError,
    inspect_original,
    one_root,
    summarize,
)


def item(name: str, eligibility: str, data: dict):
    return {
        "evidence_type": name, "eligible_prechange": eligibility,
        "content": json.dumps(data, separators=(",", ":"))
    }


def record(root: str = "CROOT-12345-01", case: int = 12345, *,
           issue_created: str = "2026-01-01T00:00:00Z",
           intro: str = "2026-01-02T00:00:00Z",
           issue_elig: str = "YES", method: str = "direct_commit",
           chronology: str = "COMPLETE",
           pr_created: str = "2026-01-01T12:00:00Z",
           pc_count: int = 1):
    return {
        "schema": "D_ROOT_EVIDENCE_PASS_A_v1.1",
        "root_id": root, "case_id": str(case), "pc_count": pc_count,
        "evidence_completeness": {"chronology": chronology},
        "analysis_rules": {
            "semantic_labels_present": False,
            "post_intro_evidence_may_support_creation": False,
            "only_prechange_yes_may_support_H_or_T1_T4": True,
        },
        "evidence_items": [
            item("ORIGINAL_ISSUE", issue_elig, {"created_at": issue_created}),
            item("PR_CONTEXT_NON_CAUSAL", "NO", {"created_at": pr_created}),
            item("INTRODUCTION_CHRONOLOGY", "N/A", {
                "status": "resolved", "method": method,
                "confidence": "high", "timestamp": intro
            }),
            item("EXACT_PRODUCING_CHANGE_AND_DIFF", "NO", {"change": "diff"})
        ]
    }


class PassAChronologyCohortTests(unittest.TestCase):
    def test_source_SHA_and_byte_count_pinned(self):
        self.assertEqual(ORIGINAL_SIZE, 25549416)
        self.assertEqual(ORIGINAL_SHA256,
                         "4510cd4dacf218c918b82d4dfde4afefee270ba5b147a5558e7dbe87e486e8c0")

    def test_issue_created_before_exact_exported_anchor_is_only_a_source_relation(self):
        r = one_root(record())
        self.assertEqual(r["issue_eligibility"], "YES")
        self.assertEqual(r["issue_anchor_relation"],
                         "ISSUE_CREATED_NO_LATER_THAN_ALL_EXPORTED_ANCHORS")
        self.assertFalse(r["review_flags"])
        self.assertEqual(r["introduction_resolved_item_count"], 1)

    def test_case154_false_early_feature_anchor_replication(self):
        src = record(
            root=CASE154_ROOT, case=154, issue_elig="NO",
            issue_created="2025-11-04T02:39:26Z",
            intro="2025-11-04T02:38:57Z",
            method="cumulative_diff_anchor",
            pr_created="2025-11-04T02:40:13Z",
        )
        row = one_root(src)
        self.assertEqual(row["issue_anchor_relation"],
                         "ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS")
        self.assertEqual(row["original_case154_anchor_time"],
                         "2025-11-04T02:38:57+00:00")
        self.assertIn("CUMULATIVE_DIFF_ANCHOR_REQUIRES_TARGET_LINE_GIT_VERIFICATION",
                      row["review_flags"])

    def test_complete_export_status_may_still_contain_no_eligible_issue(self):
        row = one_root(record(
            chronology="COMPLETE", issue_elig="NO",
            issue_created="2026-01-02T00:00:00Z",
            intro="2026-01-01T00:00:00Z"
        ))
        self.assertEqual(row["chronology"], "COMPLETE")
        self.assertEqual(row["issue_eligibility"], "NO")
        self.assertEqual(row["issue_anchor_relation"],
                         "ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS")

    def test_a_NO_eligibility_with_issue_before_all_exported_anchors_is_review_flag(self):
        row = one_root(record(issue_elig="NO"))
        self.assertIn(
            "NO_ISSUE_ELIGIBILITY_DESPITE_ISSUE_BEFORE_REPORTED_ANCHORS",
            row["review_flags"]
        )

    def test_yes_issue_eligibility_with_later_issue_is_review_flag(self):
        row = one_root(record(
            issue_elig="YES",
            issue_created="2026-01-03T00:00:00Z",
            intro="2026-01-02T00:00:00Z"
        ))
        self.assertIn(
            "YES_ISSUE_ELIGIBILITY_WITH_LATER_ISSUE_THAN_SOME_EXPORTED_ANCHORS",
            row["review_flags"]
        )

    def test_multiple_producing_changes_can_straddle_issue_date(self):
        r = record(pc_count=2)
        r["evidence_items"].append(item(
            "INTRODUCTION_CHRONOLOGY", "N/A", {
                "status": "resolved", "method": "direct_commit",
                "confidence": "high", "timestamp": "2025-12-30T00:00:00Z"
            }
        ))
        row = one_root(r)
        self.assertEqual(row["issue_anchor_relation"],
                         "MIXED_ANCHORS_OR_SAME_ROOT_MULTIPLE_PCS")
        self.assertEqual(row["introduction_item_count"], 2)
        self.assertEqual(row["introduction_resolved_item_count"], 2)

    def test_unresolved_introduction_is_not_coerced_to_prospective(self):
        r = record()
        r["evidence_items"][2]["content"] = json.dumps({
            "status": "unresolved", "timestamp": None,
            "method": "unknown", "confidence": "none",
        })
        row = one_root(r)
        self.assertEqual(row["issue_anchor_relation"], "INDETERMINATE")
        self.assertEqual(row["introduction_resolved_item_count"], 0)

    def test_invalid_issue_timestamp_fails_open_to_indeterminate_not_false_YES(self):
        row = one_root(record(issue_created="not-a-timestamp"))
        self.assertIsNone(row["issue_created"])
        self.assertEqual(row["issue_anchor_relation"], "INDETERMINATE")

    def test_timezone_offsets_are_not_silently_treated_as_UTC(self):
        row = one_root(record(issue_created="2026-01-01T02:00:00+02:00"))
        self.assertEqual(row["issue_anchor_relation"], "INDETERMINATE")

    def test_issue_created_after_PR_open_is_flagged_separately(self):
        row = one_root(record(
            issue_created="2026-01-02T02:00:00Z",
            pr_created="2026-01-01T00:00:00Z"
        ))
        self.assertIn("ISSUE_CREATED_AFTER_PR_OPENING", row["review_flags"])

    def test_no_raw_issue_body_exported(self):
        r = record()
        r["evidence_items"][0]["content"] = json.dumps({
            "created_at": "2026-01-01T00:00:00Z",
            "body": "do not export this secret fixture"
        })
        self.assertNotIn("do not export", json.dumps(one_root(r)))

    def test_synthetic_two_root_summary_no_fabricated_cohort_claim(self):
        first = one_root(record())
        second = one_root(record(
            root="CROOT-12346-01", case=12346,
            method="cumulative_diff_anchor",
            issue_elig="NO",
            chronology="INCOMPLETE",
        ))
        result = summarize([first, second], expected_roots=2,
                           expected_pcs=2, expected_cases=2)
        self.assertEqual(result["records"], 2)
        self.assertEqual(result["chronology_channel_statuses"],
                         {"COMPLETE": 1, "INCOMPLETE": 1})
        self.assertFalse(result["root_specific_Git_introduction_verified_from_this_data"])
        self.assertFalse(result["issue_body_asof_root_authenticated"])
        self.assertFalse(result["agent_received_issue_confirmed"])
        self.assertNotIn("root_ids_by_review_flag", result)

    def test_synthetic_flagged_IDs_are_opt_in(self):
        r = one_root(record(root="CROOT-12345-01", issue_elig="NO"))
        result = summarize([r], expected_roots=1,
                           expected_pcs=1, expected_cases=1,
                           include_root_ids=True)
        self.assertIn("CROOT-12345-01",
                      result["root_ids_by_review_flag"][
                          "NO_ISSUE_ELIGIBILITY_DESPITE_ISSUE_BEFORE_REPORTED_ANCHORS"])

    def test_mismatched_root_membership_is_rejected(self):
        a=one_root(record())
        with self.assertRaisesRegex(OriginalChronologyError, "duplicate"):
            summarize([a,a], expected_roots=2, expected_pcs=2, expected_cases=2)

    def test_missing_25MB_original_file_cannot_claim_census_replayed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/ORIGINAL_NAME_FOR_TEST
            p.write_bytes(b"{}\n")
            with self.assertRaisesRegex(OriginalChronologyError, "file size"):
                inspect_original(p)

    def test_original_source_symlink_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)
            file=path/"real"
            file.write_bytes(b"bad")
            link=path/"link"
            link.symlink_to(file)
            with self.assertRaisesRegex(OriginalChronologyError, "not symlink"):
                inspect_original(link)

    def test_original_schema_changed_refused(self):
        src=record()
        src["schema"]="unexpected"
        with self.assertRaisesRegex(OriginalChronologyError, "schema"):
            one_root(src)

    def test_unknown_eligibility_label_refused(self):
        src=record()
        src["evidence_items"][0]["eligible_prechange"]="CERTAIN"
        with self.assertRaisesRegex(OriginalChronologyError, "Unknown item-level"):
            one_root(src)


ORIGINAL_NAME_FOR_TEST = "D_PASS_A_EVIDENCE_342.jsonl"

if __name__ == "__main__":
    unittest.main()
