"""Fail-closed tests of the seven *illustrative*, not exhaustive, PR-advisory comparisons."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import unittest

from analysis.seven_advisory_temporal_replay_gate import (
    AdvisoryPublicationError, EXPECTED, SOURCE, audit, main,
)


def fixture():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


class SevenPostMergeAdvisoryTests(unittest.TestCase):
    def test_registered_original_root_advisory_ordering(self):
        out = audit()
        self.assertEqual(out["advisory_publications_after_merge_in_registered_sample"], 7)
        self.assertEqual(out["distinct_positive_workflows_in_registered_sample"], 6)
        self.assertEqual(out["original_matched_positive_workflows_in_registered_sample"], 5)
        self.assertEqual(out["original_unmatched_positive_workflows_in_registered_sample"], 1)
        self.assertEqual((out["calendar_day_gap_minimum"],
                          out["calendar_day_gap_maximum"]), (3, 176))

    def test_does_not_extrapolate_to_all_41_roots(self):
        out = audit()
        self.assertFalse(out["all_41_advisory_publications_audited"])
        self.assertFalse(out["prospective_security_warnings_replayed"])
        self.assertFalse(out["Wits_D2_packet_byte_sha_authenticated_in_this_CI"])
        self.assertFalse(out["external_GitHub_API_or_advisory_pages_refetched_in_this_CI"])

    def test_same_case_two_advisories_are_not_two_workflows(self):
        src = fixture()
        rows = src["observations"]
        self.assertEqual(sum(x["case_id"] == 13918 for x in rows), 2)
        self.assertEqual(len({x["case_id"] for x in rows}), 6)
        self.assertEqual(sum(x["positive_member_of_original_C2_190"] for x in rows), 5)
        self.assertEqual(len(EXPECTED), 7)

    def test_premerge_publication_mutation_rejected(self):
        src = fixture()
        src["observations"][2]["advisory_publication_calendar_date"] = "2026-01-01"
        with self.assertRaisesRegex(AdvisoryPublicationError, "source-identified"):
            audit(src)

    def test_falsely_increase_41_root_coverage_rejected(self):
        src = fixture()
        src["numerators_and_denominators"]["all_41_root_advisories_exhaustively_checked"] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "scope changed"):
            audit(src)

    def test_false_prospective_scan_rejected(self):
        src = fixture()
        src["publication_semantics"]["scanner_warning_at_PR_time_independently_replayed"] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "Unsupported historical"):
            audit(src)

    def test_upstream_GHSA_date_does_not_exclude_earlier_private_disclosure(self):
        src = fixture()
        src["publication_semantics"][
            "specific_advisory_publication_proves_earliest_possible_disclosure"
        ] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "Unsupported historical"):
            audit(src)

    def test_false_vulnerability_nonexistence_rejected(self):
        src = fixture()
        src["publication_semantics"]["vulnerability_did_not_exist_before_advisory"] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "Unsupported historical"):
            audit(src)

    def test_extra_root_advisory_record_rejected(self):
        src = fixture()
        src["observations"].append(copy.deepcopy(src["observations"][0]))
        with self.assertRaisesRegex(AdvisoryPublicationError, "root/advisory pairing"):
            audit(src)

    def test_issue_after_merge_vs_advisory_date_are_distinct(self):
        src = fixture()
        src["observations"][0]["pr_merged_utc"] = "2026-08-01T00:00:00Z"
        with self.assertRaisesRegex(AdvisoryPublicationError, "timing"):
            audit(src)

    def test_wrong_root_advisory_association_rejected(self):
        src = fixture()
        src["observations"][0]["ghsa"] = src["observations"][1]["ghsa"]
        with self.assertRaisesRegex(AdvisoryPublicationError, "root/advisory identifier"):
            audit(src)

    def test_false_original_C2_assignment_rejected(self):
        src = fixture()
        src["observations"][0]["positive_member_of_original_C2_190"] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "C2 label drift"):
            audit(src)

    def test_calendar_day_gap_is_not_elapsed_hour_count(self):
        src = fixture()
        src["observations"][3]["calendar_day_gap_utc"] = 2
        with self.assertRaisesRegex(AdvisoryPublicationError, "calendar gap"):
            audit(src)

    def test_no_original_source_rerun_claim(self):
        src = fixture()
        src["source_provenance"]["Wits_original_D2_packet_SHA256s_individually_authenticated"] = True
        with self.assertRaisesRegex(AdvisoryPublicationError, "provenance"):
            audit(src)

    def test_original_source_publication_url_rejected_if_tampered(self):
        src = fixture()
        src["observations"][0]["advisory_url"] = "https://example.com/someghsa"
        with self.assertRaisesRegex(AdvisoryPublicationError, "public provenance"):
            audit(src)

    def test_cli_does_not_export_private_original_packets(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(), 0)
        summary = json.loads(out.getvalue())
        self.assertEqual(summary["advisory_publications_after_merge_in_registered_sample"], 7)
        self.assertNotIn("P50-PC-0121", out.getvalue())
        self.assertNotIn("Mechanism Evidence", out.getvalue())


if __name__ == "__main__":
    unittest.main()
