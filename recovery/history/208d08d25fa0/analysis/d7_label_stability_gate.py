"""Bound what is and is not stable between the frozen D-final and D7 labels.

Source: the exact SHA-pinned 43-row private Git comparison ledger only.
This is a *version-consistency* audit, not inter-rater reliability,
original D or D7 source-byte authentication, or independent adjudication.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance" / "d_vs_d7_label_differences.csv"
SOURCE_GIT_BLOB_SHA1 = "93761f8742be9e6171229d60f9498ced8ee3c555"
FROZEN_ROOTS = 342
D_FINAL_ROUTE_TOTALS = {"H": 5, "T": 103, "M": 234}
D7_ROUTE_TOTALS = {"H": 6, "T": 103, "M": 233}
TIERS = {"T1", "T2", "T3", "T4", "T5", "INCOMPLETE"}


class D7StabilityError(ValueError):
    """Conflicting provenance, changed source, or inconsistent labels."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise D7StabilityError(message)


def git_blob_hash(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii")
                        + bytes((0,)) + content).hexdigest()


def inspect_rows(rows: list[dict[str, str]]) -> dict:
    """Validate source row semantics and count disagreement consequences.

    This helper is used to test malformed synthetic rows. Only audit() below
    qualifies the *real* source using its recorded Git object identity.
    """
    require(len(rows) == 43, "Expected 43 original unresolved differences")
    source_ids: set[str] = set()
    transitions = Counter()
    original = Counter()
    newer = Counter()
    workflows: dict[str, list[str]] = defaultdict(list)
    incomplete_workflows: set[str] = set()
    complete_workflows: set[str] = set()
    route_workflows: set[str] = set()
    incomplete, complete_tier, route_changed = 0, 0, 0
    for item in rows:
        root = item["root_id"]
        require(re.fullmatch(r"CROOT-[0-9]{5}-[0-9]{2}", root) is not None
                and root not in source_ids,
                "Duplicate or malformed root ID")
        source_ids.add(root)
        workflow = root.split("-")[1]
        workflows[workflow].append(root)
        a_route, b_route = item["d_final_route"], item["d7_route"]
        a_tier, b_tier = item["d_final_tier"], item["d7_tier"]
        require(item["disposition"] == "UNRESOLVED",
                "Original dispute silently adjudicated")
        require(a_route in ("H", "M") and b_route in ("H", "M") and
                (a_tier in TIERS if a_route == "M" else a_tier == "NA") and
                (b_tier in TIERS if b_route == "M" else b_tier == "NA"),
                "Unexpected route/tier code")
        require((a_route, a_tier) != (b_route, b_tier),
                "Unchanged root incorrectly represented as disagreement")
        original[a_route + "/" + a_tier] += 1
        newer[b_route + "/" + b_tier] += 1
        transitions[(a_route + "/" + a_tier, b_route + "/" + b_tier)] += 1
        if a_route != b_route:
            route_changed += 1
            route_workflows.add(workflow)
            require((a_route, a_tier, b_route, b_tier) ==
                    ("M", "T1", "H", "NA") and root == "CROOT-00649-01",
                    "Unexpected route reassignment")
        elif "INCOMPLETE" in (a_tier, b_tier):
            incomplete += 1
            incomplete_workflows.add(workflow)
        else:
            complete_tier += 1
            complete_workflows.add(workflow)
    require(route_changed == 1 and incomplete == 17 and complete_tier == 25
            and sum(transitions.values()) == 43,
            "Disagreement category counts drifted")
    require(len(workflows) == 34 and len(incomplete_workflows) == 10
            and len(complete_workflows) == 24 and len(route_workflows) == 1,
            "Workflow grouping changed")

    a_routes = Counter(k.split("/")[0] for k, n in original.items() for _ in range(n))
    b_routes = Counter(k.split("/")[0] for k, n in newer.items() for _ in range(n))
    require(a_routes == {"M": 43} and b_routes == {"M": 42, "H": 1},
            "Unexpected source route changes")
    require(sum(D_FINAL_ROUTE_TOTALS.values()) ==
            sum(D7_ROUTE_TOTALS.values()) == FROZEN_ROOTS,
            "Reported historical route totals do not sum to root census")
    require({k: D7_ROUTE_TOTALS[k] - D_FINAL_ROUTE_TOTALS[k]
             for k in D7_ROUTE_TOTALS} == {"H": 1, "T": 0, "M": -1},
            "Declared route-population shift disagrees with source")
    labels = sorted(set(original) | set(newer))
    changes = [{
        "label": label,
        "d_final_disputed_count": original[label],
        "d7_disputed_count": newer[label],
        "d7_minus_d_final": newer[label] - original[label],
        "possible_if_select_either_recorded_label":
            sum(label in (item["d_final_route"] + "/" + item["d_final_tier"],
                          item["d7_route"] + "/" + item["d7_tier"])
                for item in rows),
    } for label in labels]
    require({x["label"]: x["d7_minus_d_final"] for x in changes} == {
        "H/NA": 1, "M/INCOMPLETE": 7, "M/T1": -13,
        "M/T2": 1, "M/T3": 5, "M/T4": 3, "M/T5": -4,
    }, "Disputed tier/net-count sensitivity changed")
    require(sum(x["d7_minus_d_final"] for x in changes) == 0,
            "Category transitions do not conserve root decisions")
    common_m_roots = D7_ROUTE_TOTALS["M"]
    return {
        "status": "PASS_D_FINAL_D7_LEDGER_ONLY_CATEGORICAL_STABILITY",
        "roots_in_frozen_historical_census_source_reported": FROZEN_ROOTS,
        "unresolved_root_disagreements": len(source_ids),
        "distinct_workflows_with_disagreements": len(workflows),
        "route_changed": route_changed,
        "tier_changed_with_route_stable": incomplete + complete_tier,
        "incomplete_status_disputes": incomplete,
        "completed_tier_only_disputes": complete_tier,
        "incomplete_dispute_workflows": len(incomplete_workflows),
        "completed_tier_dispute_workflows": len(complete_workflows),
        "top_level_route_agreement_count": FROZEN_ROOTS - route_changed,
        "top_level_route_agreement_fraction": (FROZEN_ROOTS - route_changed)/FROZEN_ROOTS,
        "full_route_tier_exact_agreement_count": FROZEN_ROOTS - len(source_ids),
        "full_route_tier_exact_agreement_fraction": (FROZEN_ROOTS - len(source_ids))/FROZEN_ROOTS,
        "common_M_tier_agreement_count": common_m_roots - (incomplete + complete_tier),
        "common_M_tier_agreement_denominator": common_m_roots,
        "common_M_tier_agreement_fraction":
            (common_m_roots - incomplete - complete_tier) / common_m_roots,
        "disputed_label_version_counts": changes,
        "source_reported_D_final_route_totals": D_FINAL_ROUTE_TOTALS,
        "source_reported_D7_route_totals": D7_ROUTE_TOTALS,
        "transition_counts": [
            {"from": src, "to": dst, "roots": num}
            for (src, dst), num in sorted(transitions.items())
        ],
        "scientific_nonclaims": {
            "original_D_and_D7_full_raw_342_root_files_authenticated": False,
            "source_difference_table_independently_adjudicated": False,
            "inter_rater_reliability_estimated": False,
            "version_specific_global_T1_to_T5_denominators_authenticated": False,
            "causal_issue_to_root_relation_established": False,
        },
    }


def audit(content: bytes | None = None) -> dict:
    """Fail closed on any original 43-row file change."""
    content = SOURCE.read_bytes() if content is None else content
    require(git_blob_hash(content) == SOURCE_GIT_BLOB_SHA1,
            "Frozen 43-row Git blob SHA changed")
    try:
        rows = list(csv.DictReader(io.StringIO(content.decode("utf-8"))))
    except (UnicodeError, csv.Error) as exc:
        raise D7StabilityError("Invalid source CSV") from exc
    require(set(rows[0]) == {
        "root_id", "d_final_route", "d_final_tier", "d7_route",
        "d7_tier", "disposition", "notes",
    }, "Source schema changed")
    result = inspect_rows(rows)
    return {
        **result,
        "provenance": {
            "source_path": "provenance/d_vs_d7_label_differences.csv",
            "source_git_blob_sha1_verified": SOURCE_GIT_BLOB_SHA1,
            "audit_mode": "difference_ledger_only",
        },
    }


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
