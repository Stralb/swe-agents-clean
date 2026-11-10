"""Read-only source-labelled chronology arithmetic: C1/C2 + later continuation SQLite.

This module audits a small recorded metadata ledger, NOT original SQLite bytes
or private issue history. It never accesses the Wits cluster, GitHub, or scanner.
C1 and C2 had been independently source-hash-attested in earlier audits,
but their full SHA-256 digests were NOT recomputed in this particular pass.
Do not infer that issue-after-PR chronology establishes semantic root scope.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance" / "full3809_issue_pr_event_order_20261022.json"
STATUS = "PASS_RECORDED_CROSS_SOURCE_CHRONOLOGY_ARITHMETIC_ONLY"


class EventOrderGateError(ValueError):
    """Recorded event chronology violates frozen source accounting."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EventOrderGateError(message)


def audit(ledger: dict | None = None) -> dict:
    ledger = (json.loads(SOURCE.read_text(encoding="utf-8"))
              if ledger is None else ledger)
    require(ledger.get("schema_version") == 1 and ledger.get("status") ==
            "PASS_INDEXED_ORIGINAL_C1_C2_JOIN_TO_CANDIDATE_SQLITE_TIMING_NOT_FINAL_DB_VERIFICATION",
            "Unknown source-ledger provenance")
    prov = ledger["source_provenance"]
    for flag in ("this_query_independently_authenticates_final_20260829_sqlite_sha256",
                 "asof_issue_text_authenticated",
                 "original_C6_pairwise_semantics_available",
                 "full_file_C1_SHA256_recomputed_in_this_pass",
                 "full_file_C2_SHA256_recomputed_in_this_pass"):
        require(prov.get(flag) is False,
                f"Scientifically unsupported source-authentication claim: {flag}")
    require(prov.get("historical_linkage_snapshot") ==
            "miner.agentic-js.eval.20260720_224159.full3809-continuation.db",
            "Candidate chronology SQLite source changed")
    require(prov.get("original_C1_bytes") == 841710 and
            prov.get("original_C2_bytes") == 56175,
            "Source CSV byte lengths changed")
    for k in ("original_C1_sha256_expected_and_verified_in_separate_prior_run",
              "original_C2_sha256_expected_and_verified_in_separate_prior_run"):
        require(re.fullmatch("[0-9a-f]{64}", prov.get(k, "")) is not None,
                "Expected prior SHA-256 missing/invalid")
    require(prov["original_C1_sha256_expected_and_verified_in_separate_prior_run"] ==
            "6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b",
            "C1 separately verified SHA claim changed")
    require(prov["original_C2_sha256_expected_and_verified_in_separate_prior_run"] ==
            "4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b",
            "C2 separately verified SHA claim changed")

    counts = ledger["cohort"]
    require(counts == {"total_cases": 3809, "positive_cases": 192,
                       "negative_cases": 3617, "matched_pairs": 190},
            "Frozen C1/C2 cohort dimensions changed")
    segments = ledger["original_C1_chunked_row_census"]
    require(isinstance(segments, list) and len(segments) == 3,
            "C1 streaming census must have three segments")
    ranges = [(0, 420000), (420000, 630000), (630000, 841710)]
    segment_sums = {key: 0 for key in
                    ("records", "positive_records", "late_issue_records")}
    for i, x in enumerate(segments):
        require((x.get("start_byte"), x.get("end_byte")) == ranges[i],
                "C1 source byte segments overlap or omit data")
        for k in segment_sums:
            require(type(x.get(k)) is int and x[k] >= 0,
                    "Invalid per-segment C1 row count")
            segment_sums[k] += x[k]
        require(x["positive_records"] <= x["records"] and
                x["late_issue_records"] <= x["records"],
                "Per-segment C1 counts exceed records")
    require(segment_sums["records"] == counts["total_cases"] and
            segment_sums["positive_records"] == counts["positive_cases"],
            "Original C1 rows and positivity don't reconcile")

    bands = ledger["sqlite_join_id_range_counts"]
    expected_bands = [(1, 8000), (8001, 16000), (16001, 24000),
                      (24001, 32000), (32001, 40000), (40001, 50000)]
    require(isinstance(bands, list) and len(bands) == len(expected_bands),
            "Candidate SQLite query ranges missing")
    band_total = after_open_count = after_merge_count = 0
    for expected, x in zip(expected_bands, bands):
        require((x.get("min"), x.get("max")) == expected,
                "Candidate SQLite ID-range intervals changed")
        for k in ("n", "after_open", "after_merge"):
            require(type(x.get(k)) is int and x[k] >= 0,
                    "Invalid SQLite query tally")
        require(x["after_merge"] <= x["after_open"] <= x["n"],
                "Chronology nesting impossible")
        band_total += x["n"]
        after_open_count += x["after_open"]
        after_merge_count += x["after_merge"]
    require(band_total == counts["total_cases"],
            "Candidate SQLite 3,809-case join coverage drifted")

    ids = ledger["issue_created_after_pr_open_case_ids"]
    pos = ledger["issue_created_after_pr_open_scanner_positive_case_ids"]
    merged = ledger["issue_created_after_pr_merge_case_ids"]
    for label, arr in (("late", ids), ("positive", pos), ("after merge", merged)):
        require(isinstance(arr, list) and all(type(x) is int and
                1 <= x <= 49345 for x in arr) and arr == sorted(set(arr)),
                f"{label} case IDs must be unique, integer and sorted")
    late, positives, after_merge = set(ids), set(pos), set(merged)
    require(len(late) == after_open_count == segment_sums["late_issue_records"] == 49,
            "C1/SQLite late-issue event membership count mismatch")
    require(len(positives) == 4 and positives == {5264, 5267, 7682, 12334} and
            positives <= late, "Original C1 positive late cases drifted")
    require(len(after_merge) == after_merge_count == 5 and after_merge <= late,
            "After-merge subset and SQLite count drifted")
    require(after_merge == {11280, 16358, 16603, 37310, 44072},
            "After-merge ID membership changed")
    require(after_merge.isdisjoint(positives) and
            ledger.get("all_issue_after_merge_are_original_C1_negative") is True,
            "Original C1 after-merge label conflict")

    pairs = ledger["C2_affected_matched_pair_rows"]
    require(isinstance(pairs, list) and len(pairs) == 9,
            "Expected nine C2 pairs with reversed issue/PR timing")
    seen_pos, seen_ctrl, pos_late, ctrl_late = set(), set(), set(), set()
    both = 0
    for x in pairs:
        p, c, tier = x.get("positive"), x.get("control"), x.get("tier")
        require(type(p) is int and type(c) is int and p != c and
                p not in seen_pos and c not in seen_ctrl,
                "Duplicate/invalid matched-pair IDs")
        seen_pos.add(p)
        seen_ctrl.add(c)
        require(tier in ("A", "B"), "Unknown C2 pair tier")
        require(p in late or c in late, "Listed C2 pair unaffected by late issue")
        pos_late.update([p] if p in late else [])
        ctrl_late.update([c] if c in late else [])
        both += int(p in late and c in late)
    require(pos_late == positives and len(ctrl_late) == 6 and
            ctrl_late == {3342, 4021, 4410, 12335, 12343, 32758} and
            both == 1, "Original C2 late-side membership drifted")
    require(sum(x["tier"] == "A" for x in pairs) == 4,
            "Affected same-repo tier count unexpectedly changed")

    flags = ledger["source_interpretation_flags"]
    require(flags.get("issue_created_after_PR_open_means_linked_issue_could_not_be_original_PR_opening_instruction") is True,
            "Basic chronology inference removed")
    require(flags.get("issue_created_after_merge_means_issue_could_not_inform_that_merged_patch") is True,
            "After-merge chronology inference removed")
    for k in ("issue_created_after_PR_open_implies_no_later_PR_code_was_informed_by_issue",
              "chronology_issue_scope_and_counterfactual_causality_proven",
              "historical_source_data_modified",
              "frozen_positive_negative_labels_rewritten"):
        require(flags.get(k) is False, f"Invalid causal/frozen status: {k}")

    return {
        "status": STATUS,
        "source_C1_C2_rows_checked_against_candidate_SQLite_case_IDs": True,
        "final_frozen_SQLite_sha256_authenticated": False,
        "historical_C6_issue_content_asof_implementation_verified": False,
        "original_C1_census_cases": counts["total_cases"],
        "original_C1_positive_cases": counts["positive_cases"],
        "original_C1_negative_cases": counts["negative_cases"],
        "candidate_SQLite_matched_records": band_total,
        "issue_created_after_pr_open": len(late),
        "issue_created_after_pr_open_positive": len(positives),
        "issue_created_after_pr_open_negative": len(late-positives),
        "issue_created_after_pr_merge": len(after_merge),
        "issue_created_after_merge_positive": len(after_merge&positives),
        "affected_matched_pairs": len(pairs),
        "affected_matched_positive_cases": len(pos_late),
        "affected_matched_control_cases": len(ctrl_late),
        "affected_pairs_both_sides": both,
        "full_cohort_late_issue_fraction": len(late)/counts["total_cases"],
        "positive_late_issue_fraction": len(positives)/counts["positive_cases"],
        "negative_late_issue_fraction": len(late-positives)/counts["negative_cases"],
        "late_issues_do_not_prove_root_mechanism_explanations": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
