"""Audit candidate-DB issue chronology against original C1/C2 stored membership.

The 49 late-created-issue case IDs come from read-only queries on the later
continuation SQLite, NOT an authenticated final-August research database.

With no --c1/--c2, only committed aggregate/ID membership is checked.
With both supplied, exact independently attested C1/C2 SHA-256s are checked
before parsing, followed by all 3,809 C1 cases and 190 matched C2 pairs.
No database writes, network, historical code imports or row-level exports.
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
LEDGER = ROOT / "provenance" / "c1_c2_late_issue_chronology_census_20261023.json"
EXPECTED_C1_SHA256 = "6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b"
EXPECTED_C2_SHA256 = "4568dcadd50e827004b13c9a435c7034babce8ebf96d6a9bee49b66c9b11be2b"


class ChronologyCensusError(ValueError):
    """Unmatched membership, provenance drift or unsafe source files."""


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise ChronologyCensusError(msg)


def positive_int(x: object) -> int:
    if type(x) is int:
        require(x > 0, "Case IDs must be positive")
        return x
    require(isinstance(x, str) and re.fullmatch(r"[1-9][0-9]*", x) is not None,
            "Case IDs must be canonical positive decimal integers")
    return int(x)


def indexed_pair_membership(positive_map: dict[int, bool],
                            all_pairs: list[dict],
                            late_ids: set[int]) -> dict:
    """Classify paired cases using original C1 positive flags and C2 records."""
    require(len(positive_map) == len(set(positive_map)), "Duplicate indexed C1 IDs")
    seen_positive, seen_control = set(), set()
    affected, tiers = [], {"A": 0, "B": 0}
    for pair in all_pairs:
        p = positive_int(pair["positive_case_id"])
        c = positive_int(pair["control_case_id"])
        tier = pair["match_tier"]
        require(tier in ("A", "B") and p != c and
                p not in seen_positive and c not in seen_control,
                "Invalid matched-pair tier, identity or duplicate")
        require(positive_map.get(p) is True and positive_map.get(c) is False,
                "C2 matched positive/control status inconsistent with C1")
        seen_positive.add(p)
        seen_control.add(c)
        tiers[tier] += 1
        if p in late_ids or c in late_ids:
            affected.append({"positive_case_id": p, "control_case_id": c,
                             "match_tier": tier})
    require(seen_positive.isdisjoint(seen_control), "Positive/control sets intersect")
    affected.sort(key=lambda x: (x["positive_case_id"], x["control_case_id"]))
    return {
        "pairs": len(all_pairs),
        "tiers": tiers,
        "affected": affected,
        "late_positive_pair_count": sum(
            p["positive_case_id"] in late_ids for p in affected),
        "late_control_pair_count": sum(
            p["control_case_id"] in late_ids for p in affected),
        "both_sides_late_count": sum(
            p["positive_case_id"] in late_ids and
            p["control_case_id"] in late_ids for p in affected),
    }


def audit_recorded(ledger: dict | None = None) -> dict:
    ledger = (json.loads(LEDGER.read_text(encoding="utf-8"))
              if ledger is None else ledger)
    require(ledger.get("schema_version") == 1 and ledger.get("status") ==
            "CANDIDATE_SQLITE_CHRONOLOGY_WITH_FROZEN_C1_C2_MEMBERSHIP_VERIFIED_SOURCE_HASH_EXPECTATIONS",
            "Invalid source or census status")
    source = ledger["chronology_source"]
    require(source.get("is_authenticated_final_august_database") is False,
            "Cannot silently elevate later candidate DB to authenticated final source")
    require(source.get("all_3809_rows_recounted_by_disjoint_id_ranges") is True and
            source.get("late_id_list_independently_queried") is True,
            "Original read-only provenance flags do not match")
    c1, c2 = ledger["C1_source"], ledger["C2_source"]
    require(c1.get("expected_sha256_attested_in_earlier_recovery") ==
            EXPECTED_C1_SHA256 and
            c2.get("expected_sha256_attested_in_earlier_recovery") ==
            EXPECTED_C2_SHA256,
            "C1/C2 source SHA-256 expectations have changed")
    require(c1.get("sha256_recomputed_in_this_step") is False and
            c2.get("sha256_recomputed_in_this_step") is False,
            "Unsupported claim of fresh source authentication")
    require((c1["file_bytes"], c1["records"], c1["scanner_positive"],
             c1["scanner_negative"]) == (841710, 3809, 192, 3617),
            "C1 counts / byte length drifted")
    require((c2["file_bytes"], c2["records"], c2["tier_A"], c2["tier_B"]) ==
            (56175, 190, 115, 75), "C2 counts / byte length drifted")
    ch = ledger["chronology"]
    late_list = ch["late_created_case_ids"]
    merge_list = ch["after_pr_merged_case_ids"]
    pos_list = ch["positive_late_case_ids"]
    late = {positive_int(x) for x in late_list}
    after = {positive_int(x) for x in merge_list}
    pos = {positive_int(x) for x in pos_list}
    require(len(late) == len(late_list) == ch["late_case_count"] == 49,
            "Candidate chronology case count or uniqueness changed")
    require(len(after) == len(merge_list) == 5 and after.issubset(late),
            "After-merge cases missing, duplicate, or not after-opening")
    require(len(pos) == len(pos_list) == 4 and pos.issubset(late),
            "Late scanner-positive membership changed")
    require(pos == {5264, 5267, 7682, 12334} and after.isdisjoint(pos) and
            ch["after_merge_scanner_positive_count"] == 0 and
            ch["negative_late_count"] == len(late-pos) == 45,
            "Scanner-positive/missing after-merge status drifted")
    require(sorted(late_list) == late_list and sorted(merge_list) == merge_list and
            sorted(pos_list) == pos_list, "Case identifiers must be sorted")

    pp = ledger["C2_matching"]
    pairs = pp["affected_pairs"]
    require(isinstance(pairs, list) and len(pairs) == pp["affected_pair_count"] == 9,
            "Expected nine affected original C2 pairs")
    # Test the registered affected pairs against a minimal synthetic, complete
    # 18-case source map; the full original-C2 file is checked separately below.
    pair_ids = {positive_int(x["positive_case_id"]) for x in pairs} | {
        positive_int(x["control_case_id"]) for x in pairs}
    require(len(pair_ids) == 18, "Disjoint matched pair case identifiers changed")
    synthetic_pos = {x: False for x in pair_ids}
    for x in pairs:
        synthetic_pos[positive_int(x["positive_case_id"])] = True
    observed = indexed_pair_membership(synthetic_pos, pairs, late)
    require(observed["affected"] == sorted(pairs, key=lambda x: (
                x["positive_case_id"], x["control_case_id"])) and
            observed["tiers"] == {"A": 4, "B": 5} and
            observed["late_positive_pair_count"] == 4 and
            observed["late_control_pair_count"] == 6 and
            observed["both_sides_late_count"] == 1,
            "Affected frozen C2 pair registry / late membership mismatch")
    require(pp.get("affected_tier_A") == 4 and pp.get("affected_tier_B") == 5 and
            pp.get("late_positive_case_count_in_C2") == 4 and
            pp.get("late_control_case_count_in_C2") == 6 and
            pp.get("one_pair_has_both_late") is True,
            "C2 affected pair summary mismatch")
    scientific = ledger["science_limits"]
    require(scientific.get("issue_created_after_PR_open_does_not_imply_no_later_issue_influence")
            is True and scientific.get("issue_created_after_PR_merged_precludes_issue_influence_before_merge")
            is True and scientific.get("issue_body_as_of_root_not_authenticated") is True and
            scientific.get("original_frozen_cohort_changed") is False and
            scientific.get("original_C6_test_recomputed") is False and
            scientific.get("full_SQLite_final_sha_verified") is False and
            scientific.get("D7_annotations_changed") is False,
            "Unverified source, causal or reclassification claim")
    return {
        "status": "PASS_RECORDED_CANDIDATE_CHRONOLOGY_C1_C2_MEMBERSHIP_ARITHMETIC",
        "full_staged_C1_C2_bytes_authenticated": False,
        "final_august_SQLite_authenticated": False,
        "after_PR_open_case_count": 49,
        "positive_late": 4,
        "negative_late": 45,
        "after_merge_case_count": 5,
        "positive_after_merge": 0,
        "C2_affected_pairs": 9,
        "C2_affected_pairs_tier_A": 4,
        "C2_affected_pairs_tier_B": 5,
        "C2_positive_late": 4,
        "C2_control_late": 6,
        "C2_both_late": 1,
    }


def _read_hashed_csv(path: Path, expected_hash: str, size: int) -> list[dict]:
    require(path.is_file() and not path.is_symlink(), "Missing or symlinked source CSV")
    require(path.stat().st_size == size, "Original source CSV byte size mismatch")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        content = stream.read(size + 1)
    require(len(content) == size, "Source changed during reading")
    h.update(content)
    require(h.hexdigest() == expected_hash, "Original source CSV SHA-256 mismatch")
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8", errors="strict"))))
    except (UnicodeError, csv.Error) as exc:
        raise ChronologyCensusError("Invalid UTF-8 or CSV data") from exc
    return rows


def verify_staged(c1_path: Path, c2_path: Path,
                  ledger: dict | None = None) -> dict:
    stored = audit_recorded(ledger)
    ledger = (json.loads(LEDGER.read_text(encoding="utf-8"))
              if ledger is None else ledger)
    c1 = _read_hashed_csv(c1_path, EXPECTED_C1_SHA256, 841710)
    c2 = _read_hashed_csv(c2_path, EXPECTED_C2_SHA256, 56175)
    require(len(c1) == 3809 and len(c2) == 190,
            "C1 and C2 original record denominators are wrong")
    classifications = {}
    for row in c1:
        ident = positive_int(row["case_id"])
        require(ident not in classifications and row["is_positive"] in ("0", "1"),
                "Invalid/duplicated C1 case or scanner-positive label")
        classifications[ident] = row["is_positive"] == "1"
    require(sum(classifications.values()) == 192, "C1 positivity mismatch")
    late = set(ledger["chronology"]["late_created_case_ids"])
    after = set(ledger["chronology"]["after_pr_merged_case_ids"])
    positive = {x for x in late if classifications.get(x) is True}
    require(late.issubset(classifications) and
            positive == set(ledger["chronology"]["positive_late_case_ids"]) and
            not any(classifications.get(x) for x in after),
            "Late issue C1 membership/positivity mismatch")
    result = indexed_pair_membership(classifications, c2, late)
    registered = sorted(ledger["C2_matching"]["affected_pairs"],
                        key=lambda x: (x["positive_case_id"], x["control_case_id"]))
    require(result["pairs"] == 190 and result["tiers"] == {"A": 115, "B": 75} and
            result["affected"] == registered,
            "Frozen C2 affected pair list does not match original CSV")
    return {
        **stored,
        "status": "PASS_EXACT_SHA256_C1_C2_ROWS_AND_CANDIDATE_CHRONOLOGY_JOIN",
        "full_staged_C1_C2_bytes_authenticated": True,
        "final_august_SQLite_authenticated": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c1", type=Path, help="Original private C1 CSV")
    parser.add_argument("--c2", type=Path, help="Original private C2 CSV")
    args = parser.parse_args(argv)
    if (args.c1 is None) != (args.c2 is None):
        parser.error("Provide both --c1 and --c2, or neither")
    output = (audit_recorded() if args.c1 is None else
              verify_staged(args.c1, args.c2))
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
