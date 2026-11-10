"""Validate archived D evidence-channel coverage against the 43 D/D7 disputes.

An exact-SHA optional original-index audit is available with --index; CI
checks only the committed, derived 43-root projection. Neither mode is an
independent adjudication, original full D labels replay or inter-rater study.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "provenance" / "d7_original_evidence_export_channel_crosswalk_20261023.json"
DIFFERENCES = ROOT / "provenance" / "d_vs_d7_label_differences.csv"
LATE_ROOT_SOURCE = ROOT / "provenance" / "late_issue_four_positive_root_scope_20261022.json"
EXPECTED_SHA256 = "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6"
EXPECTED_GIT_BLOB = "93761f8742be9e6171229d60f9498ced8ee3c555"
EXPECTED_INDEX_BYTES = 47826
CHRONOLOGY_OK = "COMPLETE"
EXT_STATES = {"URLS_PRESENT_UNFETCHED", "NOT_APPLICABLE"}


class DExportChannelError(ValueError):
    """Untrusted input, source drift, or unsupported scientific claim."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise DExportChannelError(message)


def git_blob_sha1(blob: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(blob)).encode("ascii") + bytes((0,)) + blob
    ).hexdigest()


def read_csv(blob: bytes) -> list[dict[str, str]]:
    try:
        text = blob.decode("utf-8", errors="strict")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise DExportChannelError("Unparsable source CSV") from exc
    require(bool(rows) and all(None not in r for r in rows),
            "Empty CSV or malformed columns")
    return rows


def audit(*, source_ledger: dict | None = None,
          original_index_csv: bytes | None = None) -> dict:
    x = json.loads(LEDGER.read_text(encoding="utf-8")) if source_ledger is None else source_ledger
    require(x.get("schema_version") == 1 and x.get("status") ==
            "PASS_ORIGINAL_342_ROOT_EVIDENCE_INDEX_AUTHENTICATED_CROSSWALK_NO_SEMANTIC_ADJUDICATION",
            "Wrong index projection or source-state declaration")
    source = x["sources"]
    require(source.get("wits_index_bytes") == EXPECTED_INDEX_BYTES and
            source.get("wits_index_sha256_full_bytes_observed_this_conversation")
            == EXPECTED_SHA256 and
            source.get("wits_index_archived_manifest_sha256") == EXPECTED_SHA256,
            "Original evidence-index SHA/length provenance drifted")
    require(source.get("github_diff_blob_sha1") == EXPECTED_GIT_BLOB and
            source.get("wits_source_rows") == 342 and
            source.get("wits_evidence_export_semantic_analysis_performed") is False,
            "Ledger falsely claims semantic reconstruction")
    for key in (
        "original_full_D_and_D7_342_classifications_replayed",
        "D3_build_failure_proves_no_adjudication_anywhere",
        "export_chronology_COMPLETE_proves_asof_issue_body_available",
        "semantic_INCOMPLETE_equals_export_chronology_INCOMPLETE",
        "unfetched_URLS_automatically_material",
        "original_classification_edits_performed",
    ):
        require(x["limits"].get(key) is False,
                "Unsafe provenance or unverified semantic claim: " + key)

    difference_blob = DIFFERENCES.read_bytes()
    require(git_blob_sha1(difference_blob) == EXPECTED_GIT_BLOB,
            "43-root Git difference source changed")
    ds = read_csv(difference_blob)
    require(len(ds) == 43 and
            len({r["root_id"] for r in ds}) == 43 and
            all(r["disposition"] == "UNRESOLVED" for r in ds),
            "Unexpected D/D7 dispute population")
    by_id = {r["root_id"]: r for r in ds}

    projection = x["disputed_root_channel_projection"]
    require(len(projection) == 43 and
            {r["root_id"] for r in projection} == set(by_id),
            "Missing or duplicate projected disputed roots")
    seen = set()
    for r in projection:
        root = r["root_id"]
        require(root not in seen, "Duplicate projected disputed root")
        seen.add(root)
        frozen = by_id[root]
        expected_orig = frozen["d_final_route"] + "/" + frozen["d_final_tier"]
        expected_d7 = frozen["d7_route"] + "/" + frozen["d7_tier"]
        require(r["original"] == expected_orig and r["d7"] == expected_d7,
                "Projected D/D7 tiers modified")
        require(r["export_chronology"] == CHRONOLOGY_OK and
                r["export_external_guidance"] in EXT_STATES,
                "Unexpected export evidence-channel state")
        marked_incomplete = ("INCOMPLETE" in (frozen["d_final_tier"],
                                               frozen["d7_tier"]))
        require(r["semantic_incomplete_disagreement"] is marked_incomplete,
                "Semantic INCOMPLETE presence changed")

    late_source_blob = LATE_ROOT_SOURCE.read_bytes()
    require(git_blob_sha1(late_source_blob) ==
            source.get("four_late_positive_cases_issue_scope_blob_sha1"),
            "Four-case issue/root source Git blob changed")
    late_source = json.loads(late_source_blob.decode("utf-8"))
    require(late_source.get("status") ==
            "EXPLORATORY_READONLY_PUBLIC_LINKAGE_SCOPE_TRIAGE_NO_LABEL_CHANGES",
            "Late-issue source status has changed")
    require(source.get("four_late_positive_cases_timestamp_source_is_final_august_SQLite_authenticated")
            is False, "Incorrect claim of final database authentication")
    for field in (
        "export_complete_implies_linked_issue_preceded_root",
        "export_complete_implies_issue_describes_root_workstream",
        "four_late_issues_caused_scanner_roots",
    ):
        require(x["limits"].get(field) is False, "Unsupported prospective root claim: "+field)
    grouped = late_source["reviewed_issue_after_pr_positive_cases"]
    require(len(grouped) == 4 and
            {c["case_id"] for c in grouped} == {5264, 5267, 7682, 12334},
            "Four source-backed late issue cases changed")
    expected_late_roots = {
        rid: (c["case_id"], c["root_issue_scope_review"])
        for c in grouped for rid in c["root_ids"]
    }
    late_projected = x.get("late_issue_positive_root_channel_projection")
    require(isinstance(late_projected, list) and len(late_projected) ==
            len(expected_late_roots) == 14 and
            {r["root_id"] for r in late_projected} == set(expected_late_roots),
            "Four-case 14-root projection/source membership changed")
    require(len({r["root_id"] for r in late_projected}) == 14,
            "Duplicate four-case projected root")
    for r in late_projected:
        case_id, workstream = expected_late_roots[r["root_id"]]
        require(r["case_id"] == case_id and
                r["source_task_scope"] == workstream and
                r["source_case_issue_created_after_PR_open_from_candidate_SQLite"] is True,
                "Four-case source case identity/coverage modified")
        require(r["export_chronology"] == "COMPLETE" and
                r["export_external_guidance"] ==
                ("URLS_PRESENT_UNFETCHED" if case_id == 12334 else "NOT_APPLICABLE") and
                r["export_project_instructions"] ==
                ("NOT_APPLICABLE" if case_id == 5267 else "COMPLETE"),
                "Four-case original export channel metadata modified")
    require(sum(r["source_task_scope"] == "DISTINCT_PR_WORKSTREAM_IN_DIFF"
                for r in late_projected) == 12, "Distinct issue/root workstream count changed")

    labels = x["counts"]
    require(labels["exported_evidence_roots"] == 342 and
            labels["differences"] == 43 and
            labels["export_chronology_incomplete_all"] == 41 and
            labels["export_chronology_incomplete_among_disputed"] == 0 and
            labels["export_chronology_incomplete_among_other"] == 41 and
            labels["external_unfetched_all"] == 134 and
            labels["external_unfetched_among_other"] == 116,
            "Original 342-root export summary changed")
    uncertain = [r for r in projection
                 if r["semantic_incomplete_disagreement"]]
    unretrieved = [r for r in projection
                   if r["export_external_guidance"] == "URLS_PRESENT_UNFETCHED"]
    t5 = [r for r in projection
          if r["original"] == "M/T5" and r["d7"] == "M/INCOMPLETE"]
    require(len(unretrieved) == labels["external_unfetched_among_disputed"] == 18
            and len(uncertain) == labels["semantic_incomplete_disagreements"] == 17
            and sum(r in unretrieved for r in uncertain) ==
            labels["semantic_incomplete_with_unfetched_links"] == 6
            and len(uncertain) - sum(r in unretrieved for r in uncertain) ==
            labels["semantic_incomplete_with_external_NA"] == 11
            and len(t5) == labels["T5_to_incomplete_disagreements"] == 4
            and sum(r not in unretrieved for r in t5) ==
            labels["T5_to_incomplete_with_external_NA"] == 4,
            "43-root original-source channel overlap totals changed")
    require({r["root_id"] for r in t5} ==
            {"CROOT-05267-01", "CROOT-05267-02",
             "CROOT-05267-04", "CROOT-05267-07"},
            "Four T5 disputes changed")

    require(labels["four_issue_after_PR_positive_cases"] == 4 and
            labels["four_case_root_count"] == 14 and
            labels["four_case_export_chronology_COMPLETE"] == 14 and
            labels["four_case_export_external_unfetched"] == 1 and
            labels["two_separate_feature_workstreams_roots"] == 12 and
            labels["two_separate_feature_workstreams_export_chronology_COMPLETE"] == 12,
            "Late issue original exporter completeness counts changed")

    has_original = original_index_csv is not None
    if has_original:
        require(len(original_index_csv) == EXPECTED_INDEX_BYTES and
                hashlib.sha256(original_index_csv).hexdigest() == EXPECTED_SHA256,
                "Supplied original 342-root evidence index fails SHA-256")
        index = read_csv(original_index_csv)
        require(len(index) == 342 and
                len({r["root_id"] for r in index}) == 342,
                "Original D evidence index does not contain 342 distinct roots")
        source_index = {r["root_id"]: r for r in index}
        require(sum(r["channel_chronology"] == "INCOMPLETE" for r in index) == 41
                and sum(r["channel_external_guidance"] == "URLS_PRESENT_UNFETCHED"
                        for r in index) == 134,
                "Original 342-root channel census drifted")
        for r in projection:
            source_row = source_index.get(r["root_id"])
            require(source_row is not None and
                    r["export_chronology"] ==
                    source_row["channel_chronology"] and
                    r["export_external_guidance"] ==
                    source_row["channel_external_guidance"],
                    "Projected disputed root does not match authenticated source")
        for r in late_projected:
            source_row = source_index.get(r["root_id"])
            require(source_row is not None and
                    r["export_chronology"] == source_row["channel_chronology"] and
                    r["export_external_guidance"] == source_row["channel_external_guidance"] and
                    r["export_project_instructions"] == source_row["channel_project_instructions"],
                    "Four-case projected root does not match authenticated source")

    return {
        "status": ("PASS_SHA256_ORIGINAL_D_EXPORT_AND_43_ROOT_CHANNEL_CROSSWALK"
                   if has_original else
                   "PASS_RECORDED_43_ROOT_EXPORT_CHANNEL_PROJECTION_ONLY"),
        "exact_original_342_root_evidence_index_SHA256_checked_now": has_original,
        "original_full_D_and_D7_classifications_replayed": False,
        "T5_disputes_adjudicated": False,
        "root_count": 342,
        "dispute_count": 43,
        "disputed_roots_with_incomplete_export_chronology": 0,
        "chronology_incomplete_others": 41,
        "disputed_roots_with_unfetched_external_guidance": 18,
        "disputed_semantic_INCOMPLETE_with_external_NA": 11,
        "T5_to_INCOMPLETE_with_complete_chronology_and_external_NA": 4,
        "late_issue_positive_roots_with_export_chronology_COMPLETE": 14,
        "separate_PR_feature_roots_with_export_chronology_COMPLETE": 12,
        "export_complete_proves_linked_issue_was_prospective": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original-index", type=Path,
                        help="Optional authorized original Wits 342-root index CSV")
    args = parser.parse_args(argv)
    original = None
    if args.original_index is not None:
        src = args.original_index
        require(src.is_file() and not src.is_symlink(),
                "Original source path must be an existing regular file, not a symlink")
        require(src.stat().st_size == EXPECTED_INDEX_BYTES,
                "Staged original D evidence index byte length mismatch")
        original = src.read_bytes()
    print(json.dumps(audit(original_index_csv=original),
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
