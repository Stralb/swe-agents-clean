"""Source-pinned tests for the original 342-root D2 A/B evidence-stage audit.

Tests without private source files validate recorded provenance only.
Optional runtime replay in d2_packet_index_archival_stage_gate independently
checks exact three original Wits SHA-256 files and source indexing.
"""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.d2_packet_index_archival_stage_gate import (
    D2ArchiveCrosswalkError,
    DIFF_BLOB_SHA,
    DIFFERENCES,
    EXPECTED,
    METADATA,
    audit,
    git_blob_sha1,
    main,
    recompute,
)


def fixture() -> dict:
    return json.loads(METADATA.read_text(encoding="utf-8"))


class D2PacketIndexStageGateTests(unittest.TestCase):
    def test_recorded_source_packet_names_complete_without_claiming_semantic_labels(self):
        r = audit()
        self.assertEqual(r["D2_A_and_blind_B_packet_names_in_original_checksum_manifest"], 684)
        self.assertFalse(r["original_Wits_raw_D2_archive_and_export_bytes_SHA_checked_now"])
        self.assertFalse(r["historical_D_final_D7_full_labels_reauthenticated"])
        self.assertFalse(r["issue_available_before_root_verified"])
        self.assertFalse(r["source_packet_hash_listing_is_semantic_adjudication"])

    def test_distinct_D2_and_later_export_stage_status(self):
        r = audit()
        self.assertEqual(r["D2_original_explicit_chronology_fields_available"], 0)
        self.assertEqual(r["later_D_export_chronology_complete"], 301)
        self.assertEqual(r["later_D_export_chronology_incomplete"], 41)

    def test_original_phase7_evidence_and_D7_semantic_disputes_have_limited_overlap(self):
        r = audit()
        self.assertEqual(r["D2_original_explicit_phase7_correction_evidence_available"], 18)
        self.assertEqual(r["D2_correction_evidence_roots_overlapping_43_D_D7_disagreements"], 6)
        manifest = fixture()
        self.assertEqual(len(manifest["correction_flagged_outside_diff"]), 12)
        self.assertEqual(manifest["counts"]["disputed_without_D2_explicit_phase7_correction"], 37)

    def test_independent_D2_and_archived_checksum_digests_pinned(self):
        self.assertEqual(EXPECTED["d2_index"], (
            35656, "2e525ebb3af2a30a2276d4cc306a7c5eb92b42df93b2e11d078eb911ba633305",
        ))
        self.assertEqual(EXPECTED["archive_sha"], (
            63478, "5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b",
        ))
        self.assertEqual(git_blob_sha1(DIFFERENCES.read_bytes()), DIFF_BLOB_SHA)

    def test_six_explicit_correction_and_D_final_D7_conflict_identifiers(self):
        self.assertEqual(set(fixture()["disputed_with_explicit_phase7_correction"]), {
            "CROOT-00181-01", "CROOT-04309-01", "CROOT-05264-03",
            "CROOT-08147-01", "CROOT-15703-01", "CROOT-18777-01",
        })

    def test_falsely_promoting_D2_packet_archive_to_D_semantics_rejected(self):
        x = fixture()
        x["source_semantics"]["D2_A_B_packet_hash_manifest_implies_D_final_labels_produced"] = True
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "Unsupported chronology"):
            audit(metadata=x)

    def test_falsely_claiming_D2_no_chronology_flag_means_no_dates_anywhere_rejected(self):
        x = fixture()
        x["source_semantics"]["D2_explicit_chronology_fields_false_proves_no_timestamp_anywhere"] = True
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "Unsupported chronology"):
            audit(metadata=x)

    def test_falsely_claiming_later_complete_means_prospective_issue_rejected(self):
        x = fixture()
        x["source_semantics"]["later_D_export_chronology_COMPLETE_implies_issue_was_available_pre_root"] = True
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "Unsupported chronology"):
            audit(metadata=x)

    def test_changed_dispute_overlap_count_rejected(self):
        x = fixture()
        x["counts"]["disputed_with_D2_explicit_phase7_correction"] = 7
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "overlap"):
            audit(metadata=x)

    def test_wrong_SHA_for_archived_manifest_rejected(self):
        x = fixture()
        x["sources"]["original_D2_SHA_manifest"][
            "sha256_independently_verified_via_complete_text_bytes"
        ] = "0" * 64
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "provenance"):
            audit(metadata=x)

    def test_missing_one_of_three_original_staged_files_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            index = Path(td)/"D2_PACKET_INDEX_342.csv"
            index.write_bytes(b"fake")
            with self.assertRaisesRegex(D2ArchiveCrosswalkError, "all three"):
                audit(d2=index)

    def test_symlinked_staged_original_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            source = t/"target"
            source.write_bytes(b"fake")
            alias = t/"symlink.csv"
            alias.symlink_to(source)
            with self.assertRaisesRegex(D2ArchiveCrosswalkError, "non-symlink"):
                audit(d2=alias, export=source, sha_manifest=source)

    def test_short_raw_source_rejected_before_csv_parse(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            p = t/"d2.csv"
            p.write_bytes(b"fake")
            with self.assertRaisesRegex(D2ArchiveCrosswalkError, "byte count"):
                audit(d2=p, export=p, sha_manifest=p)

    def test_exact_length_but_wrong_index_digest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            p = t/"d2.csv"
            p.write_bytes(b"X"*35656)
            with self.assertRaisesRegex(D2ArchiveCrosswalkError, "SHA256"):
                audit(d2=p, export=p, sha_manifest=p)

    def test_malformed_synthetic_source_rejected_without_claiming_replay(self):
        with self.assertRaisesRegex(D2ArchiveCrosswalkError, "population changed"):
            recompute(
                d2_index=b"root_id\nX\n", export_index=b"root_id\nX\n",
                archived_sha=b"", disagreement_bytes=DIFFERENCES.read_bytes(),
            )

    def test_default_cli_emits_only_aggregate_data(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main([]), 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["D2_original_explicit_chronology_fields_available"], 0)
        self.assertNotIn("DR0001", output.getvalue())
        self.assertNotIn("CROOT-00181-01", output.getvalue())


if __name__ == "__main__":
    unittest.main()
