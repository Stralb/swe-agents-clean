"""Adversarial (non-statistical) M-route bounds for lockfile-rich root exclusions.

Inputs are source-reported historical D-final/D7 route totals and the
source-identified 36-root outlier / all 41 chronology-INCOMPLETE roots.
We do NOT know the true labels of the 36/41 roots and never guess T or M.
Removing them here is a *thought experiment*, not an edit to frozen data,
a pre-registered decision, an empirical subset rerun or an iid-root test.
"""
from __future__ import annotations

from dataclasses import dataclass
import json

from analysis.d7_label_stability_gate import (
    D7_ROUTE_TOTALS, D_FINAL_ROUTE_TOTALS, FROZEN_ROOTS, audit as audit_d7
)
from analysis.d_chronology_lockfile_concentration_gate import audit as audit_roots


@dataclass(frozen=True)
class RemovalBounds:
    label_version: str
    removed_scope: str
    original_root_count: int
    original_H: int
    original_T: int
    original_M: int
    removed_roots: int
    remaining_roots: int
    min_removed_M: int
    max_removed_M: int
    min_remaining_M: int
    max_remaining_M: int
    lower_M_fraction: float
    upper_M_fraction: float
    M_majority_robust: bool

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def compute_bounds(version: str, routes: dict[str, int],
                   scope: str, remove: int) -> RemovalBounds:
    if set(routes) != {"H", "T", "M"} or any(
        type(x) is not int or x < 0 for x in routes.values()
    ):
        raise ValueError("Expected nonnegative integer H/T/M counts")
    total = sum(routes.values())
    if total <= 0 or type(remove) is not int or not (0 <= remove < total):
        raise ValueError("Removal size must preserve at least one root")
    # We cannot remove more than all M roots; equally at least enough M
    # must be removed if the non-M population cannot cover the exclusion.
    min_removed_M = max(0, remove - routes["H"] - routes["T"])
    max_removed_M = min(routes["M"], remove)
    remaining = total - remove
    min_M = routes["M"] - max_removed_M
    max_M = routes["M"] - min_removed_M
    return RemovalBounds(
        label_version=version, removed_scope=scope,
        original_root_count=total,
        original_H=routes["H"], original_T=routes["T"],
        original_M=routes["M"],
        removed_roots=remove,
        remaining_roots=remaining,
        min_removed_M=min_removed_M,
        max_removed_M=max_removed_M,
        min_remaining_M=min_M, max_remaining_M=max_M,
        lower_M_fraction=min_M/remaining,
        upper_M_fraction=max_M/remaining,
        M_majority_robust=(min_M * 2 > remaining)
    )


def audit() -> dict:
    d = audit_d7()
    roots = audit_roots()
    if d["unresolved_root_disagreements"] != 43 or (
        d["source_reported_D_final_route_totals"] != D_FINAL_ROUTE_TOTALS
    ) or d["source_reported_D7_route_totals"] != D7_ROUTE_TOTALS:
        raise ValueError("Original D-final/D7 summary provenance mismatch")
    if roots["chronology_incomplete_export_roots"] != 41 or (
        roots["case13918_lockfile_roots"] != 36
    ) or roots["chronology_incomplete_root_workflows"] != 6 or (
        roots["frozen_D_final_D7_disagreement_overlap"] != 0
    ):
        raise ValueError("Original 41-root export missingness provenance mismatch")
    scenarios = []
    for version, labels in (("D-final", D_FINAL_ROUTE_TOTALS),
                            ("D7", D7_ROUTE_TOTALS)):
        if sum(labels.values()) != FROZEN_ROOTS:
            raise ValueError("Original D route totals not 342")
        for group, n in (("case_13918_lockfile_roots", 36),
                         ("all_export_chronology_INCOMPLETE_roots", 41)):
            scenarios.append(compute_bounds(version, labels, group, n).to_dict())
    if not all(x["M_majority_robust"] for x in scenarios):
        raise ValueError("Source-reported M majority not robust to unknown labels")
    return {
        "status": "PASS_SOURCE_REPORTED_D_ROUTE_MAJORITY_WORST_CASE_36_AND_41_REMOVAL",
        "estimand": "Root-level M plurality/majority conditional on source-reported H/T/M totals",
        "frozen_root_census": FROZEN_ROOTS,
        "adversarial_bounds_not_statistical_CIs": True,
        "original_36_or_41_root_H_T_M_labels_authenticated": False,
        "historical_D_final_D7_complete_342_label_files_reauthenticated": False,
        "root_exclusions_applied_to_actual_dataset": False,
        "C6_190_paired_statistics_recomputed": False,
        "independent_root_observations_assumed": False,
        "all_four_minimum_M_fractions_above_one_half": True,
        "scenarios": scenarios,
    }


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
