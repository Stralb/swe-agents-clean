"""Regression test: a D-export's high-confidence early anchor is not the target line."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from analysis.case154_root_introduction_timing_gate import (
    FROZEN_ROOT_LINE,
    RootIntroductionError,
    SOURCE,
    audit,
    main,
    seconds_between,
)


def fixture():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


class TargetLineTemporalEligibilityTests(unittest.TestCase):
    def test_original_wrong_anchor_vs_first_actual_git_target_line(self):
        result = audit()
        self.assertEqual(result["source_reported_early_anchor_before_issue_seconds"], 29)
        self.assertEqual(result["actual_target_line_commit_after_issue_seconds"], 990)
        self.assertTrue(result["early_cumulative_diff_anchor_is_not_target_line_introduction"])
        self.assertTrue(result["linked_issue_temporally_exists_before_target_line"])
        self.assertFalse(result["original_NO_to_YES_label_changed"])

    def test_github_source_comparisons_have_two_earlier_absences_and_later_presence(self):
        rows = fixture()["observations"]
        self.assertEqual(
            [r["source_target_line_present"] for r in rows],
            [False, False, False, True, True]
        )
        self.assertEqual(rows[1]["commit_utc"], "2025-11-04T02:38:57Z")
        self.assertEqual(rows[2]["commit_utc"], "2025-11-04T02:45:52Z")
        self.assertEqual(rows[3]["commit_utc"], "2025-11-04T02:55:56Z")
        self.assertIn("phpTagRegex", FROZEN_ROOT_LINE)

    def test_root_specific_time_gap_not_simple_issue_before_PR_heuristic(self):
        self.assertEqual(seconds_between("2025-11-04T02:38:57Z",
                                         "2025-11-04T02:39:26Z"), 29)
        self.assertEqual(seconds_between("2025-11-04T02:39:26Z",
                                         "2025-11-04T02:40:13Z"), 47)
        self.assertEqual(seconds_between("2025-11-04T02:39:26Z",
                                         "2025-11-04T02:55:56Z"), 990)
        self.assertEqual(seconds_between("2025-11-04T02:38:57Z",
                                         "2025-11-04T02:55:56Z"), 1019)

    def test_unknown_asof_issue_text_and_prompt_not_resolved(self):
        obj = audit()
        self.assertFalse(obj["exact_issue_body_asof_target_verified"])
        self.assertFalse(obj["agent_received_that_issue_verified"])
        self.assertFalse(obj["original_D_semantic_route_labels_recovered"])

    def test_original_wits_D2_packet_SHA_is_archived_and_source_pinned(self):
        x = fixture()["source_provenance"]
        self.assertEqual(x["Wits_root_packet"]["sha256"],
                         "002e258d355ecd4ffcf63ecdc7bb2e2aa4d414cb11e1807283c0f0be2c9b1558")
        self.assertTrue(x["Wits_root_packet"]["archived_D2_SHA256SUMS_matches"])
        self.assertEqual(x["Wits_later_Pass_A"]["introduction_method"],
                         "cumulative_diff_anchor")
        self.assertEqual(x["Wits_later_Pass_A"]["introduction_confidence"], "high")
        self.assertEqual(x["Wits_later_Pass_A"]["original_issue_prechange_eligibility"],
                         "NO")

    def test_source_target_line_absent_before_later_commit_must_not_flip(self):
        x = fixture()
        x["observations"][1]["source_target_line_present"] = True
        with self.assertRaisesRegex(RootIntroductionError, "source-presence"):
            audit(record=x)

    def test_source_target_line_missing_at_newer_commit_rejected(self):
        x = fixture()
        x["observations"][3]["source_target_line_present"] = False
        with self.assertRaisesRegex(RootIntroductionError, "source-presence"):
            audit(record=x)

    def test_wrong_public_git_sha_or_blob_rejected(self):
        x = fixture()
        x["observations"][3]["source_blob_sha1"] = "0"*40
        with self.assertRaisesRegex(RootIntroductionError, "source-presence"):
            audit(record=x)

    def test_wrong_original_introduction_anchor_rejected(self):
        x = fixture()
        x["source_provenance"]["Wits_later_Pass_A"][
            "recorded_root_introduction_timestamp_utc"] = "2025-11-04T02:55:56Z"
        with self.assertRaisesRegex(RootIntroductionError, "eligibility record"):
            audit(record=x)

    def test_issue_visibility_does_not_prove_exact_asof_body(self):
        x = fixture()
        x["scientific_assessment"][
            "original_issue_body_exact_version_asof_target_commit_authenticated"] = True
        with self.assertRaisesRegex(RootIntroductionError, "Unsupported causal"):
            audit(record=x)

    def test_original_historical_issue_NO_not_silently_adjudicated_YES(self):
        x = fixture()
        x["scientific_assessment"][
            "Wits_original_issue_item_prechange_YES_now_definitively_proven"] = True
        with self.assertRaisesRegex(RootIntroductionError, "Unsupported causal"):
            audit(record=x)

    def test_wrong_issue_creation_timing_rejected(self):
        x = fixture()
        x["source_provenance"]["GitHub_public_source"][
            "issue_created_at_utc"] = "2025-11-04T03:59:26Z"
        with self.assertRaisesRegex(RootIntroductionError, "Public issue/PR"):
            audit(record=x)

    def test_staged_Wits_D2_source_short_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"CROOT-00154-01.json"
            p.write_bytes(b"{}")
            with self.assertRaisesRegex(RootIntroductionError, "source invalid"):
                audit(original_wits_D2_root=p)

    def test_staged_git_repo_requires_existing_non_symlink_directory(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"not_really_git"
            p.write_text("not a repo")
            with self.assertRaisesRegex(RootIntroductionError, "real local directory"):
                audit(staged_git=p)

    def test_unstaged_CI_does_not_claim_refetched_source(self):
        out = audit()
        self.assertFalse(out["original_public_Git_snapshots_reread_now"])
        self.assertFalse(out["original_Wits_D2_source_rehashed_now"])

    def test_cli_output_summarizes_not_full_private_packet(self):
        buf=io.StringIO()
        with patch.object(sys, "argv", ["case154_audit"]):
            with contextlib.redirect_stdout(buf):
                self.assertEqual(main(), 0)
        data=json.loads(buf.getvalue())
        self.assertEqual(data["actual_target_line_commit_after_issue_seconds"], 990)
        self.assertNotIn("CROOT-00154-01",buf.getvalue())


if __name__ == "__main__":
    unittest.main()
