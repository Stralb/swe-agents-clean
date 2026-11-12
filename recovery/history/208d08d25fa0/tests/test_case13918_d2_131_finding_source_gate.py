"""Source-pinned D2 root-to-finding accounting and fail-closed provenance tests."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from analysis.case13918_d2_131_finding_source_gate import (
    FindingCensusError, MANIFEST, check, ids_from_rule_source, main,
)


def fixture():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


class Case13918D2FindingCensusTests(unittest.TestCase):
    def test_original_archived_SHA_manifest_36_of_690_source_match(self):
        src = fixture()["original_D2_archived_checksum_manifest"]
        self.assertEqual(src["unique_checksum_entries"], 690)
        self.assertEqual(src["matches_live_complete_source_SHA256_for_all_36_packets"], 36)
        self.assertEqual(src["checksum_mismatches"], 0)
        self.assertEqual(src["size_bytes"], 63478)
        self.assertFalse(check()[
            "original_archived_690_entry_D2_SHA_manifest_reauthenticated_in_this_execution"])

    def test_tampered_original_archived_manifest_record_rejected(self):
        src = fixture()
        src["original_D2_archived_checksum_manifest"]["checksum_mismatches"] = 1
        with self.assertRaisesRegex(FindingCensusError, "690-entry"):
            check(src)

    def test_staged_wrong_archive_checksum_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "SHA256SUMS.txt"
            fake.write_bytes(b"abc")
            with self.assertRaisesRegex(FindingCensusError, "byte size"):
                check(original_archive_manifest_path=fake)

    def test_staged_sha_archive_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td) / "fake"
            target.write_bytes(b"abc")
            linked=Path(td) / "SHA256SUMS.txt"
            linked.symlink_to(target)
            with self.assertRaisesRegex(FindingCensusError, "symlinked"):
                check(original_archive_manifest_path=linked)

    def test_complete_original_D2_manifest_36_roots_131_findings(self):
        result = check()
        self.assertEqual(result["roots"], 36)
        self.assertEqual(result["producing_changes"], 36)
        self.assertEqual(result["distinct_canonical_scanner_findings"], 131)
        self.assertEqual(result["largest_two_roots_scanner_findings"], 51)
        self.assertEqual(result["distinct_npm_package_names"], 33)
        self.assertEqual(result["multiple_root_package_names"], 3)
        self.assertFalse(result["case13918_in_original_190_matched_pairs"])

    def test_36_original_individual_packet_SHA256_and_full_chunk_lengths(self):
        src = fixture()
        rows = src["per_root"]
        self.assertEqual(len(rows), 36)
        self.assertEqual(sum(x["original_d2_bytes"] for x in rows), 319315)
        self.assertTrue(all(0 < x["original_d2_bytes"] < 32768 for x in rows))
        self.assertEqual(len({x["original_d2_sha256"] for x in rows}), 36)
        self.assertFalse(src["source_acquisition"]["original_36_packet_raw_bytes_committed_to_Git"])

    def test_all_original_canonical_source_IDs_exactly_cover_range(self):
        rows = fixture()["per_root"]
        ids = [x for r in rows for x in r["canonical_finding_ids"]]
        self.assertEqual(len(ids), 131)
        self.assertEqual(len(set(ids)), 131)
        self.assertEqual(set(ids), {f"CF-{n:04d}" for n in range(929, 1060)})

    def test_distinct_dependency_versions_are_not_new_workflows(self):
        rows = fixture()["per_root"]
        self.assertEqual(sum(x["package_name"] == "fast-uri" for x in rows), 2)
        self.assertEqual(sum(x["package_name"] == "minimatch" for x in rows), 2)
        self.assertEqual(sum(x["package_name"] == "picomatch" for x in rows), 2)
        self.assertEqual({r["version"] for r in rows
                          if r["package_name"] == "fast-uri"}, {"2.4.0", "3.1.0"})

    def test_same_CVE_in_two_resolved_dependency_versions(self):
        out = check()
        self.assertEqual(out["CVE_identifiers_repeated_across_two_dependency_versions"], 10)
        recorded = fixture()["cross_version_CVE_repetition"]["observed_pairs"]
        self.assertEqual({x["package_name"] for x in recorded},
                         {"fast-uri", "minimatch", "picomatch"})
        self.assertEqual(sum(len(x["repeated_CVE_ids"]) for x in recorded), 10)

    def test_all_three_2025_labelled_CVEs_publicly_published_postmerge(self):
        out = check()
        self.assertEqual(out["public_advisory_dates_postmerge_for_2025_labelled_CVEs"], 3)
        rows = fixture()["publication_sanity_checks_CVE_2025"]["records"]
        self.assertEqual({x["cve"] for x in rows}, {
            "CVE-2025-69873", "CVE-2025-13465", "CVE-2025-15284",
        })

    def test_temporal_fallacy_guard_for_disclosure_date(self):
        src = fixture()
        src["publication_sanity_checks_CVE_2025"][
            "first_publication_date_earlier_than_GHSA_ruled_out"] = True
        with self.assertRaisesRegex(FindingCensusError, "publication-audit"):
            check(src)

    def test_cross_version_duplicate_CVE_count_is_pinned(self):
        src = fixture()
        src["cross_version_CVE_repetition"][
            "repeated_distinct_CVE_identifiers_across_6_roots"] = 11
        with self.assertRaisesRegex(FindingCensusError, "repetition count"):
            check(src)

    def test_incorrect_old_CVE_publication_date_rejected(self):
        src = fixture()
        src["publication_sanity_checks_CVE_2025"][
            "records"][0]["public_advisory_date_utc"] = "2025-12-01"
        with self.assertRaisesRegex(FindingCensusError, "publication drifted"):
            check(src)

    def test_no_independent_vulnerability_inference(self):
        out = check()
        self.assertFalse(out["scanner_findings_equate_to_independent_vulnerabilities"])
        self.assertFalse(out["advisory_publication_census_complete"])
        self.assertFalse(out["original_D_semantic_root_labels_recovered"])
        self.assertFalse(out["original_Wits_D2_packet_bytes_reauthenticated_in_this_execution"])

    def test_all_36_source_file_hashes_match_archived_manifest_record(self):
        src = fixture()
        record = src["original_D2_archived_checksum_manifest"]
        self.assertEqual(record["size_bytes"], 63478)
        self.assertEqual(record["unique_checksum_entries"], 690)
        self.assertEqual(record["original_by_root_A_case13918_entries"], 36)
        self.assertEqual(record["matches_live_complete_source_SHA256_for_all_36_packets"], 36)
        self.assertEqual(record["checksum_mismatches"], 0)
        self.assertEqual(
            record["sha256_independently_recomputed_this_session"],
            "5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b",
        )
        out = check()
        self.assertEqual(out["current_Wits_D2_packet_hashes_matched_original_archive"], 36)
        self.assertFalse(out[
            "original_archived_690_entry_D2_SHA_manifest_reauthenticated_in_this_execution"
        ])

    def test_changed_archived_manifest_original_source_sha_rejected(self):
        src = fixture()
        src["original_D2_archived_checksum_manifest"][
            "sha256_independently_recomputed_this_session"
        ] = "0" * 64
        with self.assertRaisesRegex(FindingCensusError, "690-entry D2 hash"):
            check(src)

    def test_false_successful_archived_manifest_comparison_rejected(self):
        src = fixture()
        src["original_D2_archived_checksum_manifest"][
            "matches_live_complete_source_SHA256_for_all_36_packets"
        ] = 35
        with self.assertRaisesRegex(FindingCensusError, "690-entry D2 hash"):
            check(src)

    def test_symlinked_original_archived_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            target = folder / "SHA256SUMS.txt"
            target.write_bytes(b"fake")
            alias = folder / "link"
            alias.symlink_to(target)
            with self.assertRaisesRegex(FindingCensusError, "symlinked"):
                check(original_archive_manifest_path=alias)

    def test_tampered_archived_manifest_short_file_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "SHA256SUMS.txt"
            file.write_bytes(b"fake")
            with self.assertRaisesRegex(FindingCensusError, "byte size"):
                check(original_archive_manifest_path=file)

    def test_tampered_archived_manifest_exact_size_wrong_hash_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "SHA256SUMS.txt"
            file.write_bytes(b"X"*63478)
            with self.assertRaisesRegex(FindingCensusError, "source hash"):
                check(original_archive_manifest_path=file)

    def test_root_duplicate_finding_id_rejected(self):
        src = fixture()
        src["per_root"][1]["canonical_finding_ids"][0] = (
            src["per_root"][0]["canonical_finding_ids"][0])
        with self.assertRaisesRegex(FindingCensusError, "overlap"):
            check(src)

    def test_dropped_Canonical_Finding_ID_rejected(self):
        src = fixture()
        src["per_root"][8]["canonical_finding_ids"].pop()
        with self.assertRaisesRegex(FindingCensusError, "131 denominator"):
            check(src)

    def test_wrong_frozen_source_packet_hash_rejected(self):
        src = fixture()
        src["per_root"][0]["original_d2_sha256"] = "xyz"
        with self.assertRaisesRegex(FindingCensusError, "checksum"):
            check(src)

    def test_wrong_root_dependency_version_rejected(self):
        src = fixture()
        src["per_root"][0]["package_name"] = "fast-uri"
        with self.assertRaisesRegex(FindingCensusError, "package/version"):
            check(src)

    def test_wrong_D_route_adjudication_claim_rejected(self):
        src = fixture()
        src["scientific_limits"]["original_D_final_route_labels_recovered"] = True
        with self.assertRaisesRegex(FindingCensusError, "Unsupported scanner"):
            check(src)

    def test_false_131_issues_or_vulnerabilities_claim_rejected(self):
        src = fixture()
        src["scientific_limits"]["all_131_findings_independent_vulnerabilities"] = True
        with self.assertRaisesRegex(FindingCensusError, "Unsupported scanner"):
            check(src)

    def test_staged_D2_dir_must_contain_original_byte_length(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            (folder / "CROOT-13918-01.json").write_bytes(b"{}")
            with self.assertRaisesRegex(FindingCensusError, "byte size"):
                check(original_root_dir=folder)

    def test_staged_D2_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td)
            target = folder / "target"
            target.write_bytes(b"fake")
            (folder / "CROOT-13918-01.json").symlink_to(target)
            with self.assertRaisesRegex(FindingCensusError, "symlinked"):
                check(original_root_dir=folder)

    def test_original_packet_finding_field_parsing(self):
        raw = {"pc_count": 1, "constituent_pcs": [
            {"evidence": {"Canonical Finding ID(s)": "CF-0929; CF-0930"}}
        ]}
        self.assertEqual(ids_from_rule_source(raw), ["CF-0929", "CF-0930"])
        raw["constituent_pcs"][0]["evidence"]["Canonical Finding ID(s)"] = (
            "CF-0929; CF-0929")
        with self.assertRaisesRegex(FindingCensusError, "Malformed"):
            ids_from_rule_source(raw)

    def test_cli_is_aggregate_only(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([]), 0)
        parsed = json.loads(out.getvalue())
        self.assertEqual(parsed["distinct_canonical_scanner_findings"], 131)
        self.assertNotIn("CF-0929", out.getvalue())
        self.assertNotIn("Pimzino/spec-workflow-mcp", out.getvalue())


if __name__ == "__main__":
    unittest.main()
