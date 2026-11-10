"""Source-safety checks for the 342-root export / 43 D7-difference crosswalk."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.d7_evidence_export_channel_gate import (
    DExportChannelError, LEDGER, EXPECTED_SHA256, audit, main,
)


def fixture():
    return json.loads(LEDGER.read_text(encoding="utf-8"))


class DExportEvidenceCrosswalkTests(unittest.TestCase):
    def test_pinned_projection_reconciles_all_missingness_counts(self):
        out = audit()
        self.assertEqual(out["dispute_count"], 43)
        self.assertEqual(out["root_count"], 342)
        self.assertEqual(out["disputed_roots_with_incomplete_export_chronology"], 0)
        self.assertEqual(out["chronology_incomplete_others"], 41)
        self.assertEqual(out["disputed_roots_with_unfetched_external_guidance"], 18)
        self.assertEqual(out["disputed_semantic_INCOMPLETE_with_external_NA"], 11)
        self.assertEqual(out["T5_to_INCOMPLETE_with_complete_chronology_and_external_NA"], 4)

    def test_all_four_late_issue_positive_workflow_roots_export_chronology_complete(self):
        out = audit()
        self.assertEqual(out["late_issue_positive_roots_with_export_chronology_COMPLETE"], 14)
        self.assertEqual(out["separate_PR_feature_roots_with_export_chronology_COMPLETE"], 12)
        self.assertFalse(out["export_complete_proves_linked_issue_was_prospective"])

    def test_late_issue_original_export_status_is_not_prospective_task_proof(self):
        x = fixture()
        rows = x["late_issue_positive_root_channel_projection"]
        self.assertEqual(len(rows), 14)
        self.assertTrue(all(r["export_chronology"] == "COMPLETE" for r in rows))
        self.assertEqual(sum(r["export_external_guidance"] == "URLS_PRESENT_UNFETCHED"
                             for r in rows), 1)
        self.assertEqual(sum(r["export_project_instructions"] == "NOT_APPLICABLE"
                             for r in rows), 7)
        self.assertEqual(sum(r["source_task_scope"] == "DISTINCT_PR_WORKSTREAM_IN_DIFF"
                             for r in rows), 12)

    def test_modified_late_root_channel_flag_rejected(self):
        x = fixture()
        x["late_issue_positive_root_channel_projection"][0]["export_chronology"] = (
            "INCOMPLETE")
        with self.assertRaisesRegex(DExportChannelError, "metadata modified"):
            audit(source_ledger=x)

    def test_unverified_issue_precedes_root_claim_rejected(self):
        x = fixture()
        x["limits"]["export_complete_implies_linked_issue_preceded_root"] = True
        with self.assertRaisesRegex(DExportChannelError, "Unsupported prospective"):
            audit(source_ledger=x)

    def test_late_issue_source_identity_change_rejected(self):
        x = fixture()
        x["sources"]["four_late_positive_cases_issue_scope_blob_sha1"] = "0"*40
        with self.assertRaisesRegex(DExportChannelError, "Four-case issue/root source"):
            audit(source_ledger=x)

    def test_recorded_source_flag_does_not_claim_fresh_CI_raw_bytes(self):
        out = audit()
        self.assertFalse(out["exact_original_342_root_evidence_index_SHA256_checked_now"])
        self.assertFalse(out["original_full_D_and_D7_classifications_replayed"])
        self.assertFalse(out["T5_disputes_adjudicated"])

    def test_original_sha_expectation_pinned(self):
        self.assertEqual(EXPECTED_SHA256,
                         "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6")

    def test_original_source_wrong_bytes_rejected(self):
        with self.assertRaisesRegex(DExportChannelError, "fails SHA-256"):
            audit(original_index_csv=b"fake CSV data")

    def test_fake_original_status_rejected(self):
        x = fixture()
        x["sources"]["wits_evidence_export_semantic_analysis_performed"] = True
        with self.assertRaisesRegex(DExportChannelError, "semantic reconstruction"):
            audit(source_ledger=x)

    def test_false_complete_asof_issue_content_rejected(self):
        x = fixture()
        x["limits"]["export_chronology_COMPLETE_proves_asof_issue_body_available"] = True
        with self.assertRaisesRegex(DExportChannelError, "Unsafe provenance"):
            audit(source_ledger=x)

    def test_false_t5_adjudication_provenance_rejected(self):
        x = fixture()
        x["limits"]["original_full_D_and_D7_342_classifications_replayed"] = True
        with self.assertRaisesRegex(DExportChannelError, "Unsafe provenance"):
            audit(source_ledger=x)

    def test_duplicate_projection_dispute_rejected(self):
        x = fixture()
        x["disputed_root_channel_projection"][0]["root_id"] = (
            x["disputed_root_channel_projection"][1]["root_id"])
        with self.assertRaisesRegex(DExportChannelError, "Missing or duplicate"):
            audit(source_ledger=x)

    def test_missing_original_external_url_status_rejected(self):
        x = fixture()
        row = next(r for r in x["disputed_root_channel_projection"]
                   if r["export_external_guidance"] == "URLS_PRESENT_UNFETCHED")
        row["export_external_guidance"] = "NOT_APPLICABLE"
        with self.assertRaisesRegex(DExportChannelError, "totals changed"):
            audit(source_ledger=x)

    def test_semantic_incomplete_is_not_export_chronology_incomplete(self):
        x = fixture()
        row = next(r for r in x["disputed_root_channel_projection"]
                   if r["semantic_incomplete_disagreement"])
        row["export_chronology"] = "INCOMPLETE"
        with self.assertRaisesRegex(DExportChannelError, "Unexpected export"):
            audit(source_ledger=x)

    def test_false_t5_eligibility_change_rejected(self):
        x = fixture()
        row = next(r for r in x["disputed_root_channel_projection"]
                   if r["original"] == "M/T5")
        row["export_external_guidance"] = "URLS_PRESENT_UNFETCHED"
        with self.assertRaisesRegex(DExportChannelError, "totals changed"):
            audit(source_ledger=x)

    def test_nonoriginal_symlink_and_short_source_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "index.csv"
            path.write_bytes(b"fake")
            alias = Path(td) / "link.csv"
            alias.symlink_to(path)
            for target, diagnostic in [(path, "byte length"), (alias, "symlink")]:
                with self.subTest(path=str(target)):
                    with self.assertRaisesRegex(DExportChannelError, diagnostic):
                        with contextlib.redirect_stdout(io.StringIO()):
                            main(["--original-index", str(target)])

    def test_command_output_excludes_private_raw_source_rows(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([]), 0)
        parsed = json.loads(out.getvalue())
        self.assertEqual(parsed["root_count"], 342)
        self.assertNotIn("CROOT-05267", out.getvalue())


if __name__ == "__main__":
    unittest.main()
