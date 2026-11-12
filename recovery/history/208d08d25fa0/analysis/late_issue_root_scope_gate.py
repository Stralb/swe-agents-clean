"""Audit four public issue-after-PR examples against the frozen D/D7 conflict ledger.

No historical labels are reclassified. The public issue/PR descriptions are
current snapshots, not issue text authenticated as of initial PR creation.
The SQLite chronology was queried from the later continuation DB, not the
hash-verified final research snapshot. This checks archived metadata only.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "provenance" / "late_issue_four_positive_root_scope_20261022.json"
D7_DIFF = ROOT / "provenance" / "d_vs_d7_label_differences.csv"
VALID_SCOPE = {
    "DISTINCT_PR_WORKSTREAM_IN_DIFF",
    "RELATEDNESS_UNRESOLVED_MIXED_PR",
    "RELATED_BUT_POST_PR_START",
}


class LateIssueScopeError(ValueError):
    """Invalid ledger, invalid chronology, or scientifically unsafe status."""


def require(condition: bool, msg: str) -> None:
    if not condition:
        raise LateIssueScopeError(msg)


def _when(value: str) -> datetime:
    require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", value) is not None,
        "Timestamp must be canonical UTC ISO 8601")
    try:
        out = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LateIssueScopeError("Impossible UTC timestamp") from exc
    require(out.tzinfo == timezone.utc, "Timezone mismatch")
    return out


def inspect(*, ledger: dict | None = None, differences_csv: str | None = None) -> dict:
    ledger = json.loads(SOURCE.read_text(encoding="utf-8")) if ledger is None else ledger
    differences_csv = (D7_DIFF.read_text(encoding="utf-8")
                       if differences_csv is None else differences_csv)

    require(ledger.get("schema_version") == 1 and
            ledger.get("status") ==
            "EXPLORATORY_READONLY_PUBLIC_LINKAGE_SCOPE_TRIAGE_NO_LABEL_CHANGES",
            "Not the provisional source ledger")
    prov = ledger["source_provenance"]
    for key in ("original_C6_pair_master_authenticated",
                "final_frozen_sqlite_sha256_authenticated",
                "root_level_commit_introduction_dates_authenticated"):
        require(prov.get(key) is False, f"Claimed unauthenticated source: {key}")
    for key in ("scope_labels_are_adjudicated",
                "observed_current_issue_body_proves_historical_pre_pr_body",
                "issue_created_after_PR_started_proves_issue_not_actionable_for_all_commits",
                "case_level_observations_are_statistically_independent_of_roots",
                "primary_C6_omnibus_recalculated_for_this_subset"):
        require(ledger["interpretation_limits"].get(key) is False,
                f"Unverified causal/adjudication claim: {key}")
    require(ledger["interpretation_limits"].get("do_not_drop_original_cases") is True,
            "Original cohort must stay frozen")

    rows = list(csv.DictReader(io.StringIO(differences_csv)))
    require(len(rows) == ledger.get("expected_total_conflicting_roots") == 43,
            "D/D7 difference family changed")
    disputed = set()
    for row in rows:
        rid = row.get("root_id")
        require(isinstance(rid, str) and
                re.fullmatch(r"CROOT-\d{5}-\d{2}", rid) and
                rid not in disputed and row.get("disposition") == "UNRESOLVED",
                "Malformed/duplicated or silently adjudicated root")
        disputed.add(rid)

    cases = ledger.get("reviewed_issue_after_pr_positive_cases")
    require(isinstance(cases, list) and len(cases) == 4,
            "Expected four positive issue-created-after-PR cases")
    unique_cases, unique_roots, summaries = set(), set(), []
    for record in cases:
        case = record.get("case_id")
        require(type(case) is int and case > 0 and case not in unique_cases,
                "Duplicate/invalid case")
        unique_cases.add(case)
        require(type(record.get("issue_number")) is int and
                type(record.get("pr_number")) is int and
                record["issue_number"] > 0 and record["pr_number"] > 0,
                "Missing public issue/PR number")
        require(isinstance(record.get("repository_original"), str) and
                record["repository_original"].count("/") == 1 and
                isinstance(record.get("repository_current"), str) and
                record["repository_current"].count("/") == 1, "Invalid repository identity")
        pr = _when(record["pr_created_utc"])
        issue = _when(record["issue_created_utc"])
        merge = _when(record["pr_merged_utc"])
        require(pr < issue < merge, "Issue not strictly between PR start and merge")
        scope = record.get("root_issue_scope_review")
        require(scope in VALID_SCOPE, "Unknown issue-to-root evidence classification")
        roots = record.get("root_ids")
        require(isinstance(roots, list) and bool(roots), "Empty root set")
        for rid in roots:
            require(isinstance(rid, str) and
                    re.fullmatch(r"CROOT-\d{5}-\d{2}", rid) is not None and
                    int(rid.split("-")[1]) == case and rid not in unique_roots,
                    "Incorrect, duplicate or malformed root membership")
            unique_roots.add(rid)
        if "issue_specific_fix_commit" in record:
            require(case == 5267 and re.fullmatch(
                r"[0-9a-f]{40}", record["issue_specific_fix_commit"]) is not None,
                "Unexpected issue-specific commit")
            require(issue < _when(record["issue_specific_fix_commit_utc"]) < merge,
                    "Issue-specific fix commit is not after its issue and before merge")
        conflicts = sorted(set(roots) & disputed)
        summaries.append({
            "case_id": case,
            "root_count": len(roots),
            "conflicting_root_count": len(conflicts),
            "conflicting_roots": conflicts,
            "scope_review": scope,
            "issue_created_after_PR_hours": (issue-pr).total_seconds()/3600,
            "original_linked_issue_root_scope_verified_as_causal": False,
        })
    require(unique_cases == {5264, 5267, 7682, 12334},
            "Four source-derived issue-after-PR case IDs changed")
    require(len(unique_roots) == 14 and
            ledger.get("expected_total_census_roots") == 342,
            "Source root denominator or membership count drifted")
    conflicted = sum(s["conflicting_root_count"] for s in summaries)
    require(conflicted == 8, "Recorded issue-after-PR D/D7 intersection changed")
    distinct = [x for x in summaries
                if x["scope_review"] == "DISTINCT_PR_WORKSTREAM_IN_DIFF"]
    require(len(distinct) == 2 and {x["case_id"] for x in distinct} == {5264, 5267},
            "Distinct-workstream identification changed")
    distinct_roots = sum(x["root_count"] for x in distinct)
    distinct_conflicts = sum(x["conflicting_root_count"] for x in distinct)
    require(distinct_roots == 12 and distinct_conflicts == 7,
            "Source root/workstream intersection drifted")
    return {
        "status": "PASS_EXPLORATORY_FOUR_CASE_CHRONOLOGY_SCOPE_LEDGER_ONLY",
        "candidate_sqlite_and_public_current_snapshots_only": True,
        "original_C6_pairwise_coding_recovered": False,
        "original_final_SQLite_authenticated": False,
        "historical_issue_asof_PR_content_verified": False,
        "root_level_causal_issue_influence_proven": False,
        "frozen_census_root_count": 342,
        "frozen_disputed_root_count": len(disputed),
        "late_issue_positive_case_count": len(unique_cases),
        "late_issue_positive_root_count": len(unique_roots),
        "late_issue_positive_conflicting_roots": conflicted,
        "remaining_other_roots": 342-len(unique_roots),
        "remaining_other_conflicting_roots": len(disputed)-conflicted,
        "different_PR_workstream_root_count": distinct_roots,
        "different_PR_workstream_conflicting_roots": distinct_conflicts,
        "case_rows": sorted(summaries, key=lambda x: x["case_id"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(inspect(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
