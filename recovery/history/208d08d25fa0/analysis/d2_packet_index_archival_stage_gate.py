"""Pin original D2 packet-index and archived A/B evidence-stage semantics.

Two distinct stages, do not conflate:
* D2 packet index: 342 blind-A root packets + 342 blind-B alias packets
  recorded in archived SHA256SUMS; 0/342 explicit chronology field flags.
* Later D evidence export: 301/342 chronology channel COMPLETE.

Neither a packet availability flag nor later channel completeness establishes
the exact issue text available to the agent before an individual root commit.
Neither A/B evidence packet membership nor an explicit Phase-7 correction flag
authenticates final D-final/D7 semantic labels or an adjudication outcome.

CI without the three staged raw Wits files checks only *recorded* data and the
pinned Git D/D7 differences; replay mode rehashes and crosswalks original CSV
and SHA256SUMS bytes (but not all 684 original JSON packet bodies).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "provenance" / "d2_packet_index_342_archived_stage_coverage_20261023.json"
DIFFERENCES = ROOT / "provenance" / "d_vs_d7_label_differences.csv"
EXPECTED = {
    "d2_index": (35656, "2e525ebb3af2a30a2276d4cc306a7c5eb92b42df93b2e11d078eb911ba633305"),
    "export_index": (47826, "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6"),
    "archive_sha": (63478, "5bf8ed6baece182d263be4ef1e23f39cb6eba87043c17dcce4f610444397791b"),
}
DIFF_BLOB_SHA = "93761f8742be9e6171229d60f9498ced8ee3c555"
FROZEN_COUNTS = {
    "original_D2_root_index_rows": 342,
    "unique_root_ids": 342,
    "unique_blind_B_aliases": 342,
    "archived_coder_A_per_root_packet_paths": 342,
    "archived_blind_coder_B_packet_paths": 342,
    "archived_other_export_artefacts": 6,
    "D2_has_all_seven_basic_evidence_availability_flags": True,
    "basic_availability_root_count": 342,
    "D2_explicit_chronology_fields_present": 0,
    "D2_explicit_chronology_fields_absent": 342,
    "D2_explicit_phase7_correction_present": 18,
    "D2_explicit_phase7_correction_absent": 324,
    "later_D_export_chronology_COMPLETE": 301,
    "later_D_export_chronology_INCOMPLETE": 41,
    "D_final_D7_disputed_roots": 43,
    "disputed_with_D2_explicit_phase7_correction": 6,
    "disputed_without_D2_explicit_phase7_correction": 37,
    "D2_correction_present_outside_D_final_D7_disputes": 12,
    "original_D2_index_vs_D_export_root_ID_overlap": 342,
    "D2_correction_present_and_later_export_chronology_incomplete": 0,
    "D2_correction_present_and_later_export_chronology_complete": 18,
}
EXPECTED_OVERLAP = {
    "CROOT-00181-01", "CROOT-04309-01", "CROOT-05264-03",
    "CROOT-08147-01", "CROOT-15703-01", "CROOT-18777-01",
}
BASIC_D2 = (
    "issue_title_available", "requested_goal_evidence_available",
    "exact_producing_diff_available", "repository_search_evidence_available",
    "dependency_toolchain_evidence_available",
    "counterfactual_evidence_available", "phase2_source_reference_available",
)
EXTRA = {
    "D2_CODER_A_PACKETS_342.jsonl",
    "D2_CODER_B_PACKETS_342.jsonl",
    "D2_LEAKAGE_AUDIT.json",
    "D2_PACKET_BUILD_QC.json",
    "D2_PACKET_INDEX_342.csv",
    "D2_SEALED_B_ALIAS_MAP.csv",
}


class D2ArchiveCrosswalkError(ValueError):
    """Provenance or stage interpretation invalid."""


def require(flag: bool, msg: str) -> None:
    if not flag:
        raise D2ArchiveCrosswalkError(msg)


def git_blob_sha1(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii")
                        + bytes((0,)) + content).hexdigest()


def load_raw(path: Path, name: str) -> bytes:
    size, expected_hash = EXPECTED[name]
    require(path.is_file() and not path.is_symlink(),
            "Original staged file must be a regular non-symlink: " + name)
    require(path.stat().st_size == size,
            "Original staged source byte count changed: " + name)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == expected_hash,
            "Original staged source SHA256 mismatch: " + name)
    return data


def parse_csv(data: bytes) -> list[dict[str, str]]:
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
    except (UnicodeError, csv.Error) as exc:
        raise D2ArchiveCrosswalkError("Invalid original CSV bytes") from exc
    require(bool(rows) and all(None not in r for r in rows),
            "Original CSV contains missing/extra fields")
    return rows


def recompute(*, d2_index: bytes, export_index: bytes,
              archived_sha: bytes, disagreement_bytes: bytes) -> dict:
    d2 = parse_csv(d2_index)
    exported = parse_csv(export_index)
    differences = parse_csv(disagreement_bytes)
    require(len(d2) == len(exported) == 342 and len(differences) == 43,
            "Original root/index version population changed")
    d2root = {r["root_id"]: r for r in d2}
    exproot = {r["root_id"]: r for r in exported}
    alias = [r["coder_b_alias"] for r in d2]
    ids = set(d2root)
    disputes = {r["root_id"] for r in differences}
    require(len(d2root) == len(exproot) == len(set(alias)) == 342
            and ids == set(exproot) and disputes.issubset(ids),
            "Original 342-root A/B/export membership changed")
    archive = {}
    try:
        lines = archived_sha.decode("utf-8").splitlines()
    except UnicodeError as exc:
        raise D2ArchiveCrosswalkError("Invalid archived manifest text") from exc
    for line in lines:
        m = re.fullmatch(r"([a-f0-9]{64})  (\S+)", line)
        require(m is not None, "Malformed original archived checksum line")
        digest, filename = m.groups()
        require(filename not in archive,
                "Duplicate original archived packet path")
        archive[filename] = digest
    require(len(archive) == 690,
            "Original D2 archive not 690 unique checksum entries")
    pathsA = {x for x in archive if x.startswith("by_root_A/")}
    pathsB = {x for x in archive if x.startswith("by_root_B/")}
    others = set(archive) - pathsA - pathsB
    require(len(pathsA) == len(pathsB) == 342 and others == EXTRA,
            "Original D2 342 A/342 blind B/six control files drifted")
    require(pathsA == {"by_root_A/" + x + ".json" for x in ids}
            and pathsB == {"by_root_B/" + x + ".json" for x in alias},
            "D2 packet-index IDs do not have archived A/B packet SHA references")
    require(archive["D2_PACKET_INDEX_342.csv"] == EXPECTED["d2_index"][1],
            "Index SHA in archived original manifest drifted")

    correction = {
        r["root_id"] for r in d2
        if r["explicit_phase7_correction_evidence_available"] == "True"
    }
    require(all(r["explicit_chronology_fields_available"] in
                {"True", "False"} for r in d2) and
            all(r["explicit_phase7_correction_evidence_available"] in
                {"True", "False"} for r in d2),
            "D2 evidence stage flag labels are not strictly boolean")
    complete = {r["root_id"] for r in exported
                if r["channel_chronology"] == "COMPLETE"}
    incomplete = {r["root_id"] for r in exported
                  if r["channel_chronology"] == "INCOMPLETE"}
    require(complete.isdisjoint(incomplete)
            and complete | incomplete == ids,
            "Later D export chronology status not complete partition")

    return {
        "original_D2_root_index_rows": len(d2),
        "unique_root_ids": len(ids),
        "unique_blind_B_aliases": len(set(alias)),
        "archived_coder_A_per_root_packet_paths": len(pathsA),
        "archived_blind_coder_B_packet_paths": len(pathsB),
        "archived_other_export_artefacts": len(others),
        "D2_has_all_seven_basic_evidence_availability_flags":
            all(all(r[k] == "True" for k in BASIC_D2) for r in d2),
        "basic_availability_root_count":
            sum(all(r[k] == "True" for k in BASIC_D2) for r in d2),
        "D2_explicit_chronology_fields_present":
            sum(r["explicit_chronology_fields_available"] == "True" for r in d2),
        "D2_explicit_chronology_fields_absent":
            sum(r["explicit_chronology_fields_available"] == "False" for r in d2),
        "D2_explicit_phase7_correction_present": len(correction),
        "D2_explicit_phase7_correction_absent": len(ids - correction),
        "later_D_export_chronology_COMPLETE": len(complete),
        "later_D_export_chronology_INCOMPLETE": len(incomplete),
        "D_final_D7_disputed_roots": len(disputes),
        "disputed_with_D2_explicit_phase7_correction": len(disputes & correction),
        "disputed_without_D2_explicit_phase7_correction": len(disputes-correction),
        "D2_correction_present_outside_D_final_D7_disputes": len(correction-disputes),
        "original_D2_index_vs_D_export_root_ID_overlap": len(ids),
        "D2_correction_present_and_later_export_chronology_incomplete":
            len(correction & incomplete),
        "D2_correction_present_and_later_export_chronology_complete":
            len(correction & complete),
        "_overlap_ids": sorted(disputes & correction),
        "_other_corrected_ids": sorted(correction-disputes),
    }


def audit(*, metadata: dict | None = None, d2: Path | None = None,
          export: Path | None = None, sha_manifest: Path | None = None) -> dict:
    flags = [x is not None for x in (d2, export, sha_manifest)]
    require(all(flags) or not any(flags),
            "Supply all three original files or none")
    x = json.loads(METADATA.read_text(encoding="utf-8")) if metadata is None else metadata
    require(x.get("schema_version") == 1 and x.get("status") ==
            "PASS_ARCHIVED_WITS_D2_PACKET_INDEX_342_A_B_ALIAS_COVERAGE_AND_EVIDENCE_STAGE_SEPARATION",
            "Unexpected D2 archive-stage manifest status")
    diff_raw = DIFFERENCES.read_bytes()
    source = x["sources"]
    require(git_blob_sha1(diff_raw) == DIFF_BLOB_SHA and
            source["difference_ledger"]["git_blob_sha1"] == DIFF_BLOB_SHA
            and source["difference_ledger"]["rows"] == 43,
            "Original 43 D/D7 difference ledger Git source changed")
    mappings = [
        ("original_D2_index", "d2_index",
         "sha256_independently_verified_via_complete_raw_bytes"),
        ("original_later_D_export_index", "export_index",
         "sha256_independently_verified"),
        ("original_D2_SHA_manifest", "archive_sha",
         "sha256_independently_verified_via_complete_text_bytes")
    ]
    for src_key, e_key, hash_key in mappings:
        item = source[src_key]
        size, digest = EXPECTED[e_key]
        require(item.get("bytes") == size and item.get(hash_key) == digest,
                "Wits original D2/export source-byte provenance changed: " + src_key)
    require(source["original_D2_index"].get("matches_archived_SHA256SUMS") is True
            and source["original_D2_SHA_manifest"].get("unique_checksum_entries")
            == 690, "Archived D2 index/source-manifest linkage changed")
    require(x.get("counts") == FROZEN_COUNTS and
            set(x.get("disputed_with_explicit_phase7_correction", [])) == EXPECTED_OVERLAP
            and len(x.get("disputed_with_explicit_phase7_correction", [])) == 6
            and len(set(x.get("correction_flagged_outside_diff", []))) == 12
            and not set(x["correction_flagged_outside_diff"]) & EXPECTED_OVERLAP,
            "Original D2 phase7/D7 discrepancy overlap or evidence counts changed")
    for key in (
        "D2_explicit_chronology_fields_false_proves_no_timestamp_anywhere",
        "later_D_export_chronology_COMPLETE_implies_issue_was_available_pre_root",
        "phase7_explicit_correction_implies_correct_D_final_or_D7_label",
        "dispute_absent_implies_original_label_is_valid",
        "D2_A_B_packet_hash_manifest_implies_D_final_labels_produced",
        "full_342_packet_bytes_reauthenticated_from_archived_manifest",
    ):
        require(x["source_semantics"].get(key) is False,
                "Unsupported chronology, adjudication or independent-source claim: " + key)
    require(x["source_semantics"].get(
        "all_342_A_and_B_file_names_present_in_archived_manifest") is True,
        "Original Wits archive packet name coverage changed")

    staged = all(flags)
    if staged:
        result = recompute(
            d2_index=load_raw(d2, "d2_index"),
            export_index=load_raw(export, "export_index"),
            archived_sha=load_raw(sha_manifest, "archive_sha"),
            disagreement_bytes=diff_raw
        )
        overlap = result.pop("_overlap_ids")
        other = result.pop("_other_corrected_ids")
        require(result == FROZEN_COUNTS and overlap ==
                sorted(x["disputed_with_explicit_phase7_correction"]) and
                other == sorted(x["correction_flagged_outside_diff"]),
                "Raw original Wits index/archival packet crosswalk has changed")

    return {
        "status": ("PASS_ORIGINAL_D2_ARCHIVE_AND_LATER_EXPORT_FULL_SHA_REPLAY"
                   if staged else
                   "PASS_RECORDED_D2_ARCHIVED_STAGE_COVERAGE_ONLY"),
        "original_Wits_raw_D2_archive_and_export_bytes_SHA_checked_now": staged,
        "D2_A_and_blind_B_packet_names_in_original_checksum_manifest": 684,
        "D2_original_explicit_chronology_fields_available": 0,
        "later_D_export_chronology_complete": 301,
        "later_D_export_chronology_incomplete": 41,
        "D2_original_explicit_phase7_correction_evidence_available": 18,
        "D2_correction_evidence_roots_overlapping_43_D_D7_disagreements": 6,
        "historical_D_final_D7_full_labels_reauthenticated": False,
        "issue_available_before_root_verified": False,
        "source_packet_hash_listing_is_semantic_adjudication": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d2-index", type=Path, help="Original D2_PACKET_INDEX_342.csv")
    parser.add_argument("--later-export-index", type=Path,
                        help="Original D_EVIDENCE_INDEX_342.csv")
    parser.add_argument("--archived-sha-manifest", type=Path,
                        help="Original D2 SHA256SUMS.txt")
    args = parser.parse_args(argv)
    print(json.dumps(audit(d2=args.d2_index, export=args.later_export_index,
                           sha_manifest=args.archived_sha_manifest),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
