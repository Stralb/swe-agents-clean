"""Exhaustive k-pair deletion bound for original C6 Stuart-Maxwell omnibus tests.

Uses only indexed, not SHA-authenticated C6 paired categorical counts.
This exhausts allocations of k removals to contingency CELLS, not identities
of chronology-affected pairs. For goal alignment, the rare 'Unclear' category
can disappear; its originally fixed-four-class covariance is then singular.
A separately marked, *new* rank-adaptive sensitivity removes zero-marginal
categories before testing. This is not the archived historical procedure
or a familywise post-deletion multiple-testing correction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.c6_c7_indexed_omnibus import (
    AGGREGATES, AggregateReplayError, _load, stuart_maxwell,
)

EXPECTED = {
    "Instruction specificity": {
        "categories": ["Explicit instruction", "Problem only", "Suggests solution"],
        "counts": [[98, 15, 8], [25, 10, 1], [25, 8, 0]],
    },
    "Goal alignment": {
        "categories": ["Aligned", "Diverged", "Expanded", "Unclear"],
        "counts": [[155, 2, 3, 0], [7, 1, 1, 0], [19, 0, 0, 0], [2, 0, 0, 0]],
    },
}


class OmnibusDeletionError(ValueError):
    """Unsafe input, singular active table, or source accounting drift."""


def require(x: bool, reason: str) -> None:
    if not x:
        raise OmnibusDeletionError(reason)


def _source(aggregate: dict | None) -> dict:
    if aggregate is None:
        aggregate = _load(AGGREGATES)
    require(aggregate.get("schema_version") == 1 and aggregate.get("status") ==
            "INDEXED_TABLE_COUNTS_ONLY_ORIGINAL_C6_C7_BYTES_NOT_SHA256_AUTHENTICATED",
            "Original indexed aggregate identity drifted")
    require(aggregate.get("scientific_limits", {}).get(
        "staged_original_C6_C7_csv_sha256_verified") is False,
        "Historical source bytes cannot be newly claimed authenticated")
    require(set(EXPECTED) <= set(aggregate["primary_categorical"]),
            "Original categorical hypotheses missing")
    for name, expected in EXPECTED.items():
        actual = aggregate["primary_categorical"][name]
        require(actual["counts"] == expected["counts"] and
                actual["categories"] == expected["categories"],
                "Original indexed source contingency changed")
        require(sum(map(sum, actual["counts"])) == 190,
                "C6 matched-pair denominator changed")
    return aggregate


def exhaustive_omnibus_removal(counts: list[list[int]], k: int) -> dict:
    """Enumerate ALL feasible ways to remove k records from paired square cells.

    One allocation vector stands for many identity-level subsets. It is
    sufficient to bound ANY aggregate-test value given cell totals. When a
    category has zero row and column marginal, that class is unidentifiable
    in the originally fixed-category test. We separately report a rank-adapted
    Stuart-Maxwell sensitivity omitting only structurally absent categories.
    """
    require(type(k) is int and 0 <= k < 190, "Invalid number of removed pairs")
    n = len(counts)
    require(n in (3, 4) and all(len(row) == n and
            all(type(v) is int and v >= 0 for v in row) for row in counts),
            "Unexpected paired matrix structure")
    require(sum(map(sum, counts)) == 190,
            "Frozen category-level sample size changed")
    cells = [(i, j, c) for i, row in enumerate(counts)
             for j, c in enumerate(row) if c > 0]
    removal = [0] * len(cells)
    eligible = 0
    fixed_rank = 0
    rank_adapted = 0
    nonsignificant_fixed = 0
    nonsignificant_adapted = 0
    max_fixed = None
    max_adapted = None

    def finish() -> None:
        nonlocal eligible, fixed_rank, rank_adapted
        nonlocal nonsignificant_fixed, nonsignificant_adapted
        nonlocal max_fixed, max_adapted
        next_counts = [row[:] for row in counts]
        for (i, j, _), take in zip(cells, removal):
            next_counts[i][j] -= take
        marginal_presence = [
            sum(next_counts[i]) +
            sum(next_counts[j][i] for j in range(n))
            for i in range(n)
        ]
        living = [i for i, total in enumerate(marginal_presence) if total > 0]
        require(len(living) >= 2, "Fewer than two observed categories")
        reduced = [[next_counts[i][j] for j in living] for i in living]
        try:
            result = stuart_maxwell(reduced)
        except AggregateReplayError as exc:
            raise OmnibusDeletionError(
                "Still singular after omitting only zero-marginal classes") from exc
        require(result["n_pairs_from_contingency"] == 190 - k,
                "Lost pair records during removal")
        eligible += 1
        record = {
            "p_value": result["p_value"],
            "chi_square": result["chi_square"],
            "df": result["df"],
            "alive_category_indices": living,
            "removed": [
                {"row": i, "column": j, "removed_pairs": take}
                for (i, j, _), take in zip(cells, removal) if take
            ],
        }
        if len(living) == n:
            fixed_rank += 1
            nonsignificant_fixed += int(result["p_value"] >= 0.05)
            if max_fixed is None or result["p_value"] > max_fixed["p_value"]:
                max_fixed = record
        else:
            rank_adapted += 1
            nonsignificant_adapted += int(result["p_value"] >= 0.05)
            if max_adapted is None or result["p_value"] > max_adapted["p_value"]:
                max_adapted = record

    def walk(index: int, remain: int) -> None:
        if index == len(cells):
            if remain == 0:
                finish()
            return
        cap = min(remain, cells[index][2])
        for q in range(cap + 1):
            removal[index] = q
            walk(index + 1, remain-q)

    walk(0, k)
    require(eligible > 0 and eligible == fixed_rank + rank_adapted,
            "Incomplete enumeration")
    return {
        "removed_pairs": k,
        "remaining_pairs": 190 - k,
        "number_of_nonempty_original_cells": len(cells),
        "feasible_cell_removal_allocations": eligible,
        "original_fixed_rank_test_computable_allocations": fixed_rank,
        "fixed_rank_allocations_nominal_p_at_least_0_05": nonsignificant_fixed,
        "original_fixed_rank_test_uncomputable_empty_category_allocations": rank_adapted,
        "new_rank_adaptive_empty_class_omission_allocations": rank_adapted,
        "rank_adaptive_allocations_nominal_p_at_least_0_05": nonsignificant_adapted,
        "max_p_fixed_rank": max_fixed,
        "max_p_rank_adapted": max_adapted,
    }


def audit(*, k: int = 9, aggregate: dict | None = None) -> dict:
    source = _source(aggregate)
    out = {}
    for name in EXPECTED:
        mat = source["primary_categorical"][name]["counts"]
        original = stuart_maxwell(mat)
        result = exhaustive_omnibus_removal(mat, k)
        require(original["n_pairs_from_contingency"] == 190,
                "Original Stuart-Maxwell source denominator changed")
        out[name] = {"original_primary_omnibus": original, **result}
    return {
        "status": "PASS_INDEXED_C6_EXHAUSTIVE_NINE_PAIR_OMNIBUS_BOUNDS_ONLY",
        "candidate_sqlite_affected_pairs": k,
        "assumes_any_k_of_190_pair_ids_may_be_removed": True,
        "actual_affected_pair_categorical_labels_recovered": False,
        "original_C6_paired_csv_sha256_authenticated": False,
        "original_frozen_final_sqlite_sha256_authenticated": False,
        "original_multicategory_omnibus_statistical_method_used": True,
        "rank_adaptive_drop_zero_marginal_category_is_new_sensitivity_not_historical_method": True,
        "rank_adapted_does_not_mean_final_reclassification": True,
        "original_nine_primary_familywise_postdeletion_adjustment_verified": False,
        "repository_blocked_confidence_intervals_recomputed": False,
        "causal_inference_supported": False,
        "comparisons": out,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remove-pairs", type=int, default=9)
    args = parser.parse_args(argv)
    print(json.dumps(audit(k=args.remove_pairs), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
