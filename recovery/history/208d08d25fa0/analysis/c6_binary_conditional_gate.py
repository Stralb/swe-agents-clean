"""Conditional C6 binary-test consistency, from reported marginals and live control counts.

This is not a replay of authenticated C6 master bytes. The positive marginals
and three-decimal p-values are HISTORICALLY REPORTED, while the control counts
were independently inspected read-only on Wits on 2026-10-22. No C6 labels,
GitHub records, or private case IDs are carried by this module.
"""
from __future__ import annotations

import argparse
import json
import math


class BinaryConsistencyError(ValueError):
    """Invalid aggregate evidence, unsupported rounding, or ambiguous table."""


# These aggregate-only records are documented in
# docs/C6_BINARY_CONTROL_MISSINGNESS_CONDITIONAL_REPLAY_20261022.md.
# The old catalog's prior-activity n=190 is preserved as a discrepant,
# historically reported but not independently authenticated metadata field.
OBSERVATIONS = {
    "human_review": {
        "matched_pairs_total": 190,
        "complete_pairs": 189,
        "missing_control": 1,
        "control_yes_live": 47,
        "positive_yes_pct_reported": "28.6",
        "control_yes_pct_reported": "24.9",
        "p_reported_3dp": "0.419",
        "catalog_n_reported": 189,
    },
    "any_prior_repository_activity": {
        "matched_pairs_total": 190,
        "complete_pairs": 187,
        "missing_control": 3,
        "control_yes_live": 140,
        "positive_yes_pct_reported": "70.1",
        "control_yes_pct_reported": "74.9",
        "p_reported_3dp": "0.336",
        "catalog_n_reported": 190,
    },
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BinaryConsistencyError(message)


def count_for_rounded_rate(n: int, one_decimal_percent: str) -> list[int]:
    """Enumerate integer Yes totals compatible with a displayed 0.1% rate."""
    _require(type(n) is int and 1 <= n <= 200, "Invalid complete-pair count")
    _require(isinstance(one_decimal_percent, str) and
             one_decimal_percent.count(".") == 1 and
             len(one_decimal_percent.split(".")[1]) == 1,
             "Rate must be a one-decimal string")
    try:
        x = float(one_decimal_percent)
    except ValueError as exc:
        raise BinaryConsistencyError("Non-numeric percentage") from exc
    _require(math.isfinite(x) and 0 <= x <= 100, "Percentage outside [0,100]")
    return [k for k in range(n + 1)
            if f"{100 * k / n:.1f}" == one_decimal_percent]


def exact_two_sided_mcnemar(positive_only: int, control_only: int) -> float:
    """Twice the smaller exact Binomial(n_discordant, 1/2) tail, capped at 1."""
    b, c = positive_only, control_only
    _require(type(b) is int and type(c) is int and b >= 0 and c >= 0 and
             b + c <= 200, "Invalid nonnegative discordant counts")
    n = b + c
    if n == 0:
        return 1.0
    left = sum(math.comb(n, j) for j in range(min(b, c) + 1))
    return min(1.0, 2.0 * left / (2 ** n))


def compatible_tables(*, n: int, positive_rate_1dp: str,
                      control_rate_1dp: str, p_3dp: str) -> list[dict]:
    """Find EVERY 2x2 paired table satisfying rounded marginal rates and p."""
    _require(isinstance(p_3dp, str) and p_3dp.count(".") == 1 and
             len(p_3dp.split(".")[1]) == 3, "p-value must have three decimals")
    try:
        value = float(p_3dp)
    except ValueError as exc:
        raise BinaryConsistencyError("Non-numeric p-value") from exc
    _require(math.isfinite(value) and 0 <= value <= 1, "Invalid p-value")
    candidates = []
    for pos_yes in count_for_rounded_rate(n, positive_rate_1dp):
        for ctrl_yes in count_for_rounded_rate(n, control_rate_1dp):
            low = max(0, pos_yes + ctrl_yes - n)
            high = min(pos_yes, ctrl_yes)
            for both in range(low, high + 1):
                pos_only = pos_yes - both
                ctrl_only = ctrl_yes - both
                neither = n - both - pos_only - ctrl_only
                p = exact_two_sided_mcnemar(pos_only, ctrl_only)
                if f"{p:.3f}" == p_3dp:
                    candidates.append({
                        "both_yes": both,
                        "positive_only": pos_only,
                        "control_only": ctrl_only,
                        "neither_yes": neither,
                        "positive_yes": pos_yes,
                        "control_yes": ctrl_yes,
                        "exact_two_sided_p": p,
                    })
    return candidates


def audit_recorded() -> dict:
    checks = {}
    for name, src in OBSERVATIONS.items():
        n = src["complete_pairs"]
        _require(src["matched_pairs_total"] == n + src["missing_control"],
                 "Control missingness/denominator conflict")
        control_candidates = count_for_rounded_rate(
            n, src["control_yes_pct_reported"])
        _require(control_candidates == [src["control_yes_live"]],
                 "Independently observed control count does not match report")
        tables = compatible_tables(
            n=n,
            positive_rate_1dp=src["positive_yes_pct_reported"],
            control_rate_1dp=src["control_yes_pct_reported"],
            p_3dp=src["p_reported_3dp"],
        )
        _require(len(tables) == 1,
                 "Reported marginals/p-value do not uniquely identify an exact-test table")
        table = tables[0]
        _require(sum(table[key] for key in (
            "both_yes", "positive_only", "control_only", "neither_yes")) == n,
            "Matched-pair table does not sum to complete-case denominator")
        checks[name] = {
            "complete_pairs": n,
            "missing_controls": src["missing_control"],
            "historical_catalog_n_reported": src["catalog_n_reported"],
            "historical_catalog_n_disagrees_with_effective_n":
                src["catalog_n_reported"] != n,
            "independently_observed_control_yes": src["control_yes_live"],
            "implied_positive_yes_from_reported_percentage":
                table["positive_yes"],
            "uniquely_compatible_exact_mcnemar_table": table,
            "conditional_match_to_reported_p_3dp": True,
        }
    _require(not count_for_rounded_rate(190, "70.1") and
             not count_for_rounded_rate(190, "74.9"),
             "Unexpected viability of N=190 for prior-activity rounded rates")
    return {
        "status": "PASS_REPORTED_RATE_EXACT_MCNEMAR_CONDITIONAL_CONSISTENCY_ONLY",
        "audit_date": "2026-10-22",
        "controls_read_directly_from_original_Wits_C6_context": True,
        "positive_side_marginals_independently_recovered": False,
        "original_C6_paired_master_bytes_authenticated": False,
        "original_historical_test_formula_proven": False,
        "matched_pair_joints_independently_recovered": False,
        "original_C6_results_sample_size_187_confirmed": False,
        "comparisons": checks,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output aggregate JSON")
    parser.parse_args(argv)
    result = audit_recorded()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
