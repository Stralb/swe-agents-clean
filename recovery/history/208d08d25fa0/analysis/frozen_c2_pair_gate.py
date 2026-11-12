"""Replay byte-verified frozen C2 pair structure without requiring C1.

This verifies the *existing* pair CSV, not how original candidates were
chosen, whether C1 positive labels are correct, or scanner outcomes.
Only a separately approved offline file outside Git may be supplied.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from analysis.cluster_stage_lineage import (
    StageEvidenceError, _csv_rows, audit_recorded, load_recorded, require,
)

REQUIRED = {
    "positive_case_id", "control_case_id", "match_tier",
    "positive_repository", "control_repository", "same_repository",
    "positive_opportunity_signature", "control_opportunity_signature",
    "abs_pr_time_days",
}


def _signature(value: str) -> set[str]:
    members = value.split(";")
    require(all(token and token == token.strip() for token in members) and
            len(members) == len(set(members)),
            "Malformed or duplicate scanner-opportunity token")
    return set(members)


def verify_c2_pairs_only(path: Path, data: dict,
                         *, expected_pairs: int | None = None,
                         expected_same_repo: int | None = None) -> dict:
    """Hash original CSV before parsing. Count overrides are for tests only."""
    meta = data["c2_matching"]
    required_total = 190 if expected_pairs is None else expected_pairs
    required_a = 115 if expected_same_repo is None else expected_same_repo
    require(type(required_total) is int and type(required_a) is int and
            0 <= required_a <= required_total and required_total > 0,
            "Invalid expected frozen pair total")
    rows = _csv_rows(
        path, meta["matched_pairs_sha256"], meta["matched_pairs_bytes"],
        REQUIRED, "C2 matched-control standalone",
    )
    positive_ids, control_ids = set(), set()
    groups = {"A": 0, "B": 0}
    for row in rows:
        pos, control = row["positive_case_id"], row["control_case_id"]
        require(pos.isdecimal() and control.isdecimal() and pos != control,
                "Malformed pair ID or self-matched control")
        require(pos not in positive_ids and control not in control_ids,
                "Frozen pair reused positive or control case")
        positive_ids.add(pos)
        control_ids.add(control)
        tier = row["match_tier"]
        require(tier in groups, "Unknown frozen matching tier")
        groups[tier] += 1
        pr, cr = row["positive_repository"], row["control_repository"]
        require(bool(pr.strip()) and bool(cr.strip()),
                "Missing repository identifier")
        same = pr == cr
        require(row["same_repository"] == ("1" if same else "0"),
                "same_repository bit contradicts pair repository labels")
        positive_sig = _signature(row["positive_opportunity_signature"])
        control_sig = _signature(row["control_opportunity_signature"])
        if tier == "A":
            require(same and positive_sig <= control_sig,
                    "Tier A requires same-repository opportunity superset")
        else:
            require(not same and positive_sig == control_sig,
                    "Tier B requires cross-repository exact opportunity")
        try:
            days = float(row["abs_pr_time_days"])
        except (ValueError, TypeError) as exc:
            raise StageEvidenceError("Invalid C2 matching time interval") from exc
        require(math.isfinite(days) and 0 <= days <= 90.00001,
                "C2 original ninety-day caliper violated")
    require(len(rows) == required_total and
            len(positive_ids) == len(control_ids) == required_total and
            groups["A"] == required_a and
            groups["B"] == required_total - required_a,
            "Frozen C2 pair/tier totals disagree with frozen source")
    return {
        "status": "PASS_C2_BYTES_AND_INTERNAL_PAIR_RULES_ONLY",
        "c2_source_sha256": meta["matched_pairs_sha256"],
        "bytes_verified": meta["matched_pairs_bytes"],
        "matched_pairs": len(rows),
        "distinct_positive_ids": len(positive_ids),
        "distinct_control_ids": len(control_ids),
        "tier_a_same_repo": groups["A"],
        "tier_b_cross_repo": groups["B"],
        "sha256_verified_against_frozen_metadata": True,
        "c1_positive_membership_verified": False,
        "c1_csv_sha256_verified": False,
        "matcher_optimizer_rerun": False,
        "final_historical_database_verified": False,
        "scanner_findings_reproduced": False,
        "causal_comparison_reproduced": False,
        "note": "Checks only bytes and internal invariants of a frozen pair CSV; "
                "it cannot validate positive labels or optimizer decisions without C1.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen_c2_csv", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_recorded()
        audit_recorded(data)
        result = verify_c2_pairs_only(args.frozen_c2_csv, data)
        status = 0
    except (StageEvidenceError, OSError, UnicodeError, TypeError, ValueError,
            KeyError, json.JSONDecodeError) as exc:
        result = {
            "status": "BLOCKED_C2_FILE_OR_PAIR_RULES",
            "error": str(exc),
            "original_scanner_results_reproduced": False,
        }
        status = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
