"""Worst-case removal of chronology-inverted pairs, using C6 INDEXED aggregates.

No individual pair outcome is known for the affected cases. The worst-case
over ALL ways of deleting k of 190 pairs bounds a binary category's effect
and exact two-sided McNemar p-value. This is a post-hoc sensitivity exercise,
NOT the historical Stuart-Maxwell omnibus, repository-blocked resampling,
nor independently authenticated original C6 source bytes.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from analysis.c6_binary_conditional_gate import exact_two_sided_mcnemar
from analysis.c6_indexed_pair_bootstrap_ci import (
    paired_difference_counts, AGGREGATES, SOURCE,
)

EXPECTED = {
    ("Instruction specificity", "Explicit instruction"): (23, 50, 117),
    ("Instruction specificity", "Suggests solution"): (33, 9, 148),
    ("Goal alignment", "Aligned"): (5, 28, 157),
}


class DeletionBoundError(ValueError):
    """Invalid source provenance or candidate deletion count."""


def require(flag: bool, why: str) -> None:
    if not flag:
        raise DeletionBoundError(why)


def all_k_removal_outcomes(positive_only: int, control_only: int,
                           neutral: int, k: int) -> list[dict]:
    """Exhaust exact removal of k pair records from +1/-1/0 categories."""
    sizes = (positive_only, control_only, neutral, k)
    require(all(type(x) is int and x >= 0 for x in sizes), "Counts must be nonnegative integers")
    n = sum(sizes[:3])
    require(1 <= n <= 500 and 0 <= k < n, "Remove fewer than the original pair count")
    outcomes = []
    for take_positive in range(min(k, positive_only) + 1):
        for take_control in range(min(k - take_positive, control_only) + 1):
            take_neutral = k - take_positive - take_control
            if take_neutral > neutral:
                continue
            b = positive_only - take_positive
            c = control_only - take_control
            z = neutral - take_neutral
            survivors = n - k
            require(b + c + z == survivors, "Deletion arithmetic failed")
            outcomes.append({
                "removed_positive_only": take_positive,
                "removed_control_only": take_control,
                "removed_neutral": take_neutral,
                "surviving_positive_only": b,
                "surviving_control_only": c,
                "surviving_neutral": z,
                "surviving_n": survivors,
                "paired_difference_pp": 100 * (b - c) / survivors,
                "exact_two_sided_binary_mcnemar_p": exact_two_sided_mcnemar(b, c),
            })
    require(bool(outcomes), "No feasible pair-deletion allocations")
    return outcomes


def audit(*, k: int = 9, source: dict | None = None,
          aggregates: dict | None = None) -> dict:
    source = (json.loads(Path(SOURCE).read_text(encoding="utf-8"))
              if source is None else source)
    aggregates = (json.loads(Path(AGGREGATES).read_text(encoding="utf-8"))
                  if aggregates is None else aggregates)
    require(source.get("schema_version") == 1 and source.get("status") ==
            "INDEXED_SOURCE_REPORTED_PAIR_BOOTSTRAP_CI_NOT_SOURCE_BYTE_AUTHENTICATED",
            "Source is not the original indexed C6 category representation")
    require(source.get("original_source_C6_file_bytes_authenticated") is False and
            aggregates.get("scientific_limits", {}).get(
                "staged_original_C6_C7_csv_sha256_verified") is False,
            "Input source provenance must remain explicitly unauthenticated")
    entries = source.get("source_reported_rows")
    require(isinstance(entries, list) and len(entries) == len(EXPECTED),
            "Three expected C6 category records missing")
    actual = {}
    for row in entries:
        key = (row["variable"], row["category"])
        require(key in EXPECTED and key not in actual,
                "Unknown or repeated C6 category")
        meta = aggregates["primary_categorical"][key[0]]
        require(key[1] in meta["categories"], "Missing category in matched matrix")
        i = meta["categories"].index(key[1])
        b, c, neutral = paired_difference_counts(meta["counts"], i)
        require((b, c, neutral) == EXPECTED[key], "Indexed C6 matched-pair counts drifted")
        require(row["n_pairs"] == b + c + neutral == 190 and
                row["positive_count"] - row["control_count"] == b - c,
                "Marginal counts disagree between indexed C6 sources")
        outcomes = all_k_removal_outcomes(b, c, neutral, k)
        worst = max(outcomes, key=lambda r: (
            r["exact_two_sided_binary_mcnemar_p"],
            -r["removed_neutral"],
            -r["removed_positive_only"],
        ))
        min_diff = min(r["paired_difference_pp"] for r in outcomes)
        max_diff = max(r["paired_difference_pp"] for r in outcomes)
        original_diff = 100 * (b - c) / 190
        actual[key] = {
            "original_positive_only": b,
            "original_control_only": c,
            "original_neutral": neutral,
            "original_binary_difference_pp": original_diff,
            "original_exact_binary_mcnemar_p": exact_two_sided_mcnemar(b, c),
            "surviving_n": 190 - k,
            "feasible_deletion_allocations": len(outcomes),
            "minimum_possible_difference_pp": min_diff,
            "maximum_possible_difference_pp": max_diff,
            "binary_direction_cannot_reverse":
                (min_diff > 0 if original_diff > 0 else max_diff < 0),
            "worst_case_binary_mcnemar_p": worst["exact_two_sided_binary_mcnemar_p"],
            "worst_case_allocation": worst,
            "nominal_0_05_significant_under_all_allocations":
                worst["exact_two_sided_binary_mcnemar_p"] < .05,
        }
    require(set(actual) == set(EXPECTED), "Expected source categories changed")
    return {
        "status": "PASS_INDEXED_BINARY_WORST_CASE_K_PAIR_DELETION_ONLY",
        "candidate_snapshot_affected_pairs": k,
        "candidate_snapshot_exact_final_August_DB_authenticated": False,
        "historical_C6_source_bytes_authenticated": False,
        "specific_chronology_affected_pair_outcomes_recovered": False,
        "historical_omnibus_Stuart_Maxwell_after_deletion_recomputed": False,
        "posthoc_selected_binary_indicators_not_preregistered_family": True,
        "repository_blocked_confidence_intervals_recomputed": False,
        "rows": [
            {"variable": var, "category": category, **actual[(var, category)]}
            for var, category in EXPECTED
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove-pairs", type=int, default=9)
    args = parser.parse_args(argv)
    print(json.dumps(audit(k=args.remove_pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
