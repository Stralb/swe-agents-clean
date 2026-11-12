"""Read-only C6 matched-control category reconciliation and multiplicity sensitivity.

Inputs are frozen *indexed aggregates* and source-reported p-values committed as
aggregate-only metadata. This does NOT authenticate original C6 bytes, coding,
paired binary/continuous tests, confidence intervals, or the original analysis plan.

The nine-primary Holm/BH corrections are ADDITIONAL post-hoc sensitivity analyses,
not assumed to have been part of the historic preregistered methodology.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

from analysis.c6_c7_indexed_omnibus import replay_indexed, AggregateReplayError

ROOT = Path(__file__).resolve().parents[1]
INDEXED = ROOT / "provenance" / "c6_indexed_category_and_family_20261022.json"
AGGREGATES = ROOT / "provenance" / "c6_c7_indexed_aggregate_matrices_20261022.json"
CATALOG = ROOT / "provenance" / "c6_c7_completed_source_catalog_20261022.json"
ALPHA = 0.05
NAMES = (
    "issue_instruction_specificity", "issue_purpose", "pr_goal_alignment",
    "implementation_category", "human_review", "issue_to_pr_delay",
    "same_issue_pr_author", "any_prior_repository_activity", "primary_agent_tool",
)
P_VALUE_TO_MATRIX = {
    "issue_instruction_specificity": "Instruction specificity",
    "issue_purpose": "Issue purpose",
    "pr_goal_alignment": "Goal alignment",
    "implementation_category": "Implementation category",
    "primary_agent_tool": "Primary agent/tool",
}
SECONDARY_CATEGORIES = ("PR purpose", "Requester association")


class FamilyAuditError(ValueError):
    """A frozen denominator, category identity, or provenance contract changed."""


def require(flag: bool, message: str) -> None:
    if not flag:
        raise FamilyAuditError(message)


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm (1979) step-down family-wise adjusted p-values, preserving ties."""
    _validate_pvalues(pvals)
    ordered = sorted(pvals, key=lambda name: (pvals[name], name))
    n = len(ordered)
    corrected: dict[str, float] = {}
    previous = 0.0
    for j, name in enumerate(ordered):
        previous = min(1.0, max(previous, (n - j) * pvals[name]))
        corrected[name] = previous
    return corrected


def benjamini_hochberg(pvals: dict[str, float]) -> dict[str, float]:
    """BH step-up false-discovery-rate adjusted p-values."""
    _validate_pvalues(pvals)
    ordered = sorted(pvals, key=lambda name: (pvals[name], name))
    n = len(ordered)
    corrected: dict[str, float] = {}
    next_value = 1.0
    for j in range(n - 1, -1, -1):
        name = ordered[j]
        next_value = min(next_value, pvals[name] * n / (j + 1))
        corrected[name] = next_value
    return corrected


def _validate_pvalues(pvals: dict[str, float]) -> None:
    require(isinstance(pvals, dict) and bool(pvals), "No p-values")
    require(all(isinstance(k, str) and k for k in pvals), "Invalid hypothesis ID")
    require(all(type(p) in (float, int) and math.isfinite(p) and 0 <= p <= 1
                for p in pvals.values()), "Invalid or nonfinite p-value")


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _matrix_margins(meta: dict, *, n_expected: int) -> dict[str, tuple[int, int]]:
    labels, counts = meta["categories"], meta["counts"]
    require(isinstance(labels, list) and len(labels) >= 2 and
            len(labels) == len(set(labels)) == len(counts), "Duplicate/invalid category labels")
    k = len(labels)
    require(all(isinstance(row, list) and len(row) == k and
                all(type(value) is int and value >= 0 for value in row) for row in counts),
            "Invalid categorical contingency counts")
    require(sum(map(sum, counts)) == n_expected, "Unexpected pair denominator")
    return {name: (sum(counts[i]), sum(counts[j][i] for j in range(k)))
            for i, name in enumerate(labels)}


def _read_and_validate_family(indexed: dict, catalog: dict) -> tuple[dict[str, float], dict[str, dict]]:
    require(indexed.get("schema_version") == 1 and
            indexed.get("status") == "INDEXED_C6_CATEGORY_RECONCILIATION_REPORTED_PVALUES_ONLY",
            "Unrecognized indexed source or provenance")
    require(indexed["source_representation"]["source_C6_original_file_bytes_authenticated"] is False,
            "Incorrect source-byte verification claim")
    records = indexed["historical_primary_pvalues"]
    source_records = catalog["preserved_historical_reports"]["c6_reported_primary_p_values"]
    require(indexed["expected_primary_family_size"] == len(NAMES) ==
            len(records) == len(source_records) == catalog["preserved_historical_reports"]["c6_primary_comparisons"],
            "Historical nine-primary-test family changed")
    lookup = {}
    for r in records:
        require(isinstance(r, dict) and r.get("name") in NAMES and r["name"] not in lookup,
                "Duplicate or unknown primary hypothesis")
        name, n, digits = r["name"], r["n_pairs_reported"], r["display_decimals"]
        require(type(n) is int and n == (189 if name == "human_review" else 190),
                "Incorrect original paired denominator")
        require(digits == (5 if name == "issue_instruction_specificity" else 3),
                "Unexpected reported p-value precision")
        require(r.get("input_provenance") == "HISTORICAL_REPORTED_VALUE",
                "Original p-values cannot be presented as newly recomputed")
        lookup[name] = r
    require(set(lookup) == set(NAMES), "Historical primary family incomplete")
    require(catalog["preserved_historical_reports"]["c6_human_review_missing"] == 1,
            "Missing review record was retrospectively imputed")
    require(catalog["preserved_historical_reports"]["c6_source_reported_pairs"] == 190 and
            catalog["preserved_historical_reports"]["c6_tier_a_pairs"] == 115,
            "Original matched cohort sizes changed")
    legacy = {}
    for r in source_records:
        name = r["name"]
        require(name in NAMES and name not in legacy and
                r.get("independently_recomputed") is False,
                "Historical report provenance missing/changed")
        legacy[name] = r
    require(set(lookup) == set(legacy), "Different primary comparison identities")
    for name in lookup:
        require(lookup[name]["p_reported"] == legacy[name]["p_value_source_reported"] and
                lookup[name]["n_pairs_reported"] == legacy[name]["source_reported_n"],
                "Historical p-value, sample size or name drift")
    pvalues = {name: lookup[name]["p_reported"] for name in NAMES}
    _validate_pvalues(pvalues)
    require(indexed["limitations"]["four_remaining_primary_tests_independently_recomputed"] is False and
            indexed["limitations"]["original_C6_C7_full_source_SHA256_verified"] is False,
            "Unsupported scientific reproduction claim")
    return pvalues, lookup


def audit(*, indexed: dict | None = None, aggregates: dict | None = None,
          catalog: dict | None = None) -> dict:
    indexed = _read(INDEXED) if indexed is None else indexed
    aggregates = _read(AGGREGATES) if aggregates is None else aggregates
    catalog = _read(CATALOG) if catalog is None else catalog
    pvalues, family = _read_and_validate_family(indexed, catalog)
    require(aggregates.get("schema_version") == 1 and
            aggregates.get("scientific_limits", {}).get("staged_original_C6_C7_csv_sha256_verified") is False,
            "Aggregate source provenance changed")
    primary = aggregates["primary_categorical"]
    secondary = indexed["secondary_contingency"]
    require(set(primary) == set(P_VALUE_TO_MATRIX.values()) and
            set(secondary) == set(SECONDARY_CATEGORIES), "Categorical variables changed")
    table_counts = indexed["category_effect_counts"]
    require(set(table_counts) == set(primary) | set(secondary), "C6 effect row grouping changed")
    compared = 0
    details = {}
    for group, table in {**primary, **secondary}.items():
        n = 189 if group == "Requester association" else 190
        from_contingency = _matrix_margins(table, n_expected=n)
        from_effects = table_counts[group]
        require(set(from_effects) == set(from_contingency), "C6 category coverage differs")
        for cat, observed in from_effects.items():
            require(isinstance(observed, list) and len(observed) == 2 and
                    all(type(x) is int and 0 <= x <= n for x in observed),
                    "Invalid category effect count")
            require(tuple(observed) == from_contingency[cat],
                    "Indexed category-level effect and contingency disagree")
            compared += 1
        require(sum(x[0] for x in from_effects.values()) == n and
                sum(x[1] for x in from_effects.values()) == n,
                "C6 category effect denominators not exhaustive")
        details[group] = {"n_pairs": n, "categories_verified": len(from_effects)}
    require(compared == 37, "Expected C6 category detail row count drifted")

    # Five tests were independently recalculated from the C6 *indexed count*
    # representation. The other four are kept as published rounded p-values.
    independent = replay_indexed(aggregates)["categorical_omnibus"]
    indexed_exact = {}
    for name, matrix_name in P_VALUE_TO_MATRIX.items():
        value = independent[matrix_name]["p_value"]
        indexed_exact[name] = value
        require(round(value, family[name]["display_decimals"]) == pvalues[name],
                "Historical categorical p-value disagrees with indexed matrix")

    corrected = holm(pvalues)
    fdr = benjamini_hochberg(pvalues)
    # Reported p-values are rounded. Conservative individual upper bounds use
    # Bonferroni x9, which remains valid even if close p-values change order.
    robust = {}
    for name in NAMES:
        p, digits = pvalues[name], family[name]["display_decimals"]
        half = 0.5 * 10 ** (-digits)
        lo, hi = max(0.0, p-half), min(1.0, p+half)
        if 9*hi < ALPHA:
            conclusion = "ROBUSTLY_SIGNIFICANT_EVEN_BY_WORST_CASE_BONFERRONI"
        elif lo > ALPHA:
            conclusion = "ROBUSTLY_NOT_NOMINALLY_SIGNIFICANT"
        else:
            conclusion = "UNRESOLVED_WITH_REPORTED_PRECISION"
        robust[name] = {"lower_p_from_display": lo, "upper_p_from_display": hi,
                        "conclusion": conclusion}

    is_significant = {k for k,v in corrected.items() if v < ALPHA}
    require(is_significant == {"issue_instruction_specificity", "pr_goal_alignment"} and
            all(robust[name]["conclusion"] ==
                ("ROBUSTLY_SIGNIFICANT_EVEN_BY_WORST_CASE_BONFERRONI" if name in is_significant
                 else "ROBUSTLY_NOT_NOMINALLY_SIGNIFICANT") for name in NAMES),
            "Nine-test family sensitivity unexpectedly changed")
    hybrid = dict(pvalues)
    hybrid.update(indexed_exact)
    hybrid_adjusted = holm(hybrid)
    secondary_p = catalog["preserved_historical_reports"]
    tier_a = indexed["source_reported_tier_a_sensitivity"]
    require(tier_a["n_pairs"] == 115 and
            tier_a["status"] == "REPORTED_ONLY_NOT_RECOMPUTED" and
            tier_a["instruction_specificity_nominal_p"] == secondary_p["c6_same_repository_specificity_p_source_reported"] and
            tier_a["goal_alignment_nominal_p"] == secondary_p["c6_same_repository_alignment_p_source_reported"],
            "Historical Tier-A sensitivity no longer consistent")
    return {
        "status": "PASS_INDEXED_CATEGORY_MARGINS_AND_POSTHOC_MULTIPLICITY_SENSITIVITY_ONLY",
        "observed_category_effect_rows_reconciled": compared,
        "indexed_category_details": details,
        "historical_primary_family_count": len(NAMES),
        "reported_pvalues_holm": corrected,
        "reported_pvalues_bh_fdr": fdr,
        "holm_significant_at_0_05": sorted(is_significant),
        "conservative_display_rounding_check": robust,
        "five_indexed_recomputed_pvalues": indexed_exact,
        "mixed_evidence_holm_sensitivity_five_exact_four_reported": hybrid_adjusted,
        "tier_a_nominal_pvalues_reported_only": tier_a,
        "tier_a_specificity_hypothetical_nine_test_bonferroni": min(1.0, tier_a["instruction_specificity_nominal_p"]*9),
        "tier_a_bonferroni_scope_note": "Illustrative sensitivity only: Tier-A testing family/multiplicity was not established as preregistered.",
        "historical_familywise_adjustment_originally_preregistered": False,
        "historical_semantic_labels_and_original_C6_bytes_authenticated": False,
        "four_remaining_primary_statistics_independently_recomputed": False,
        "historical_repo_blocked_resampling_recomputed": False,
        "counterfactual_causal_claim_supported": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit aggregate audit JSON (no case-level fields)")
    parser.parse_args(argv)
    try:
        result, code = audit(), 0
    except (FamilyAuditError, AggregateReplayError, ValueError, KeyError, TypeError,
            OSError, json.JSONDecodeError, ArithmeticError) as exc:
        result, code = {"status": "BLOCKED_C6_PRIMARY_FAMILY_OR_CATEGORY_AUDIT",
                        "error": str(exc), "scientific_reproduction_complete": False}, 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
