"""Offline chronology triage of original D_PASS_A_EVIDENCE_342.jsonl.

Purpose: aggregate *source-reported* root introduction chronology and item
eligibility, NOT assert actual first scanner-targeted line commit timestamps.
Case CROOT-00154-01 is an authenticated example where cumulative_diff_anchor
falsely reports an earlier feature-level commit as the target-line introduction.

This module never fetches or modifies Wits, GitHub, a database or labels. It
requires exact ORIGINAL 25,549,416 source bytes (SHA-256 checked) and reads
one JSONL root at a time. CI tests its parser using synthetic records only.
Without staged original data, it does NOT claim a full 342-root cohort replay.

Output is aggregate counts by default. --list-flagged prints case/root IDs
for explicit follow-up, never raw original issue bodies or private prompts.

Crucial: a timestamp or eligible_prechange flag is exporter-produced evidence,
not a measured first target-line commit, issue-as-of body, issue consumption
by the agent, vulnerability, ground-truth security flaw or causal effect.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ORIGINAL_SIZE = 25549416
ORIGINAL_SHA256 = "4510cd4dacf218c918b82d4dfde4afefee270ba5b147a5558e7dbe87e486e8c0"
ORIGINAL_NAME = "D_PASS_A_EVIDENCE_342.jsonl"
EXPECTED_ROOTS = 342
EXPECTED_PCS = 455
EXPECTED_CASES = 191
CASE154_ROOT = "CROOT-00154-01"


class OriginalChronologyError(ValueError):
    """The source or its temporal interpretation is incomplete/invalid."""


def require(ok: bool, message: str) -> None:
    if not ok:
        raise OriginalChronologyError(message)


def parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        v = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if v.tzinfo is None or v.utcoffset() != timezone.utc.utcoffset(None):
        return None
    return v


def json_content(item: dict) -> dict | None:
    raw = item.get("content")
    if not isinstance(raw, str):
        return None
    try:
        out = json.loads(raw)
    except (ValueError, TypeError):
        return None
    return out if isinstance(out, dict) else None


def one_root(record: dict) -> dict:
    require(record.get("schema") == "D_ROOT_EVIDENCE_PASS_A_v1.1",
            "Unexpected original Wits Pass-A packet schema")
    rid = record.get("root_id")
    pc_count = record.get("pc_count")
    require(isinstance(rid, str) and rid.startswith("CROOT-") and
            type(pc_count) is int and 1 <= pc_count <= 12,
            "Unexpected root ID or producing-change count")
    items = record.get("evidence_items")
    require(isinstance(items, list) and all(isinstance(v, dict) for v in items),
            "Missing original item-level evidence")
    completeness = record.get("evidence_completeness", {})
    chronology = completeness.get("chronology")
    require(chronology in ("COMPLETE", "INCOMPLETE"),
            "Unexpected export chronology status")
    rules = record.get("analysis_rules", {})
    require(rules.get("only_prechange_yes_may_support_H_or_T1_T4") is True
            and rules.get("post_intro_evidence_may_support_creation") is False
            and rules.get("semantic_labels_present") is False,
            "Original exporter prospective-evidence rules changed")
    event_types = Counter(str(v.get("evidence_type")) for v in items)
    issues = [v for v in items if v.get("evidence_type") == "ORIGINAL_ISSUE"]
    introductions = [v for v in items
                     if v.get("evidence_type") == "INTRODUCTION_CHRONOLOGY"]
    pr_context = [v for v in items if v.get("evidence_type") == "PR_CONTEXT_NON_CAUSAL"]
    require(len(issues) <= 1 and len(pr_context) <= 1,
            "Multiple original-issue or PR context records")
    all_elig = Counter(str(v.get("eligible_prechange", "MISSING")) for v in items)
    unexpected = set(all_elig) - {"YES", "NO", "UNKNOWN", "N/A"}
    require(not unexpected, "Unknown item-level prospective eligibility values")

    issue_data = json_content(issues[0]) if issues else None
    issue_created = parse_utc(issue_data.get("created_at")) if issue_data else None
    issue_elig = issues[0].get("eligible_prechange") if issues else "MISSING"

    pr_data = json_content(pr_context[0]) if pr_context else None
    pr_opened = parse_utc(pr_data.get("created_at")) if pr_data else None

    intro_times = []
    methods = []
    statuses = []
    confidences = []
    for v in introductions:
        d = json_content(v)
        if not d:
            methods.append("UNPARSEABLE")
            statuses.append("UNPARSEABLE")
            confidences.append("UNPARSEABLE")
            continue
        methods.append(str(d.get("method", "MISSING")))
        statuses.append(str(d.get("status", "MISSING")))
        confidences.append(str(d.get("confidence", "MISSING")))
        stamp = parse_utc(d.get("timestamp"))
        if stamp is not None and d.get("status") == "resolved":
            intro_times.append(stamp)

    all_intro_resolved = bool(introductions) and len(intro_times) == len(introductions)
    if issue_created is None or not all_intro_resolved:
        relation = "INDETERMINATE"
    elif issue_created <= min(intro_times):
        relation = "ISSUE_CREATED_NO_LATER_THAN_ALL_EXPORTED_ANCHORS"
    elif issue_created > max(intro_times):
        relation = "ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS"
    else:
        relation = "MIXED_ANCHORS_OR_SAME_ROOT_MULTIPLE_PCS"
    flagged = []
    if issue_elig == "NO" and relation == "ISSUE_CREATED_NO_LATER_THAN_ALL_EXPORTED_ANCHORS":
        flagged.append("NO_ISSUE_ELIGIBILITY_DESPITE_ISSUE_BEFORE_REPORTED_ANCHORS")
    if issue_elig == "YES" and relation in {
        "ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS",
        "MIXED_ANCHORS_OR_SAME_ROOT_MULTIPLE_PCS",
    }:
        flagged.append("YES_ISSUE_ELIGIBILITY_WITH_LATER_ISSUE_THAN_SOME_EXPORTED_ANCHORS")
    if issue_created is not None and pr_opened is not None and issue_created > pr_opened:
        flagged.append("ISSUE_CREATED_AFTER_PR_OPENING")
    if any(m == "cumulative_diff_anchor" for m in methods):
        flagged.append("CUMULATIVE_DIFF_ANCHOR_REQUIRES_TARGET_LINE_GIT_VERIFICATION")

    return {
        "root_id": rid,
        "case_id": str(record.get("case_id")),
        "pc_count": pc_count,
        "chronology": chronology,
        "item_eligibility": dict(all_elig),
        "issue_eligibility": issue_elig,
        "issue_anchor_relation": relation,
        "issue_created": issue_created.isoformat() if issue_created else None,
        "PR_created": pr_opened.isoformat() if pr_opened else None,
        "introduction_item_count": len(introductions),
        "introduction_resolved_item_count": len(intro_times),
        "anchor_methods": methods,
        "anchor_statuses": statuses,
        "anchor_confidences": confidences,
        "review_flags": flagged,
        "original_case154_anchor_time": (
            intro_times[0].isoformat() if rid == CASE154_ROOT and intro_times else None
        ),
    }


def summarize(observations: list[dict], *, expected_roots: int = EXPECTED_ROOTS,
              expected_pcs: int = EXPECTED_PCS,
              expected_cases: int = EXPECTED_CASES,
              include_root_ids: bool = False) -> dict:
    require(len(observations) == expected_roots and
            len({r["root_id"] for r in observations}) == expected_roots,
            "Wrong or duplicate original 342-root source membership")
    require(sum(r["pc_count"] for r in observations) == expected_pcs,
            "Original 455 producing-change membership drifted")
    require(len({r["case_id"] for r in observations}) == expected_cases,
            "Original 191 root-bearing case cohort drifted")
    flagcounts = Counter(f for r in observations for f in r["review_flags"])
    eligcounts = Counter(r["issue_eligibility"] for r in observations)
    relations = Counter(r["issue_anchor_relation"] for r in observations)
    chrono = Counter(r["chronology"] for r in observations)
    methods = Counter(m for r in observations for m in r["anchor_methods"])
    itemelig = Counter()
    for r in observations:
        itemelig.update(r["item_eligibility"])
    case154 = [r for r in observations if r["root_id"] == CASE154_ROOT]
    if expected_roots == EXPECTED_ROOTS:
        require(len(case154) == 1, "Source Pass-A missing anchored case154 root")
        root = case154[0]
        require(root["original_case154_anchor_time"] ==
                "2025-11-04T02:38:57+00:00"
                and root["issue_eligibility"] == "NO" and
                root["issue_anchor_relation"] ==
                "ISSUE_CREATED_AFTER_ALL_EXPORTED_ANCHORS",
                "Original 154 root early feature-level timing finding not reproduced")
        require(chrono == {"COMPLETE": 301, "INCOMPLETE": 41},
                "Original full Pass-A chrono channel counts differ from D export index")
    output = {
        "status": "PASS_SOURCE_REPORTED_PASS_A_TEMPORAL_ELIGIBILITY_TRIAGE",
        "records": len(observations),
        "root_bearing_workflows": len({r["case_id"] for r in observations}),
        "source_producing_changes": sum(r["pc_count"] for r in observations),
        "chronology_channel_statuses": dict(sorted(chrono.items())),
        "original_issue_prechange_eligibility": dict(sorted(eligcounts.items())),
        "issue_vs_exported_anchor_relation": dict(sorted(relations.items())),
        "introduction_method_occurrences": dict(sorted(methods.items())),
        "item_eligibility_values": dict(sorted(itemelig.items())),
        "review_flags": dict(sorted(flagcounts.items())),
        "root_specific_Git_introduction_verified_from_this_data": False,
        "historical_H_T_M_or_T1_T5_labels_recovered": False,
        "issue_body_asof_root_authenticated": False,
        "agent_received_issue_confirmed": False,
        "contemporaneous_security_warning_available_proven": False,
        "issue_after_exported_anchor_is_actual_issue_after_target_line": False,
        "source_event_flags_are_false_issue_labels_without_target_Git_check": False,
    }
    if include_root_ids:
        output["root_ids_by_review_flag"] = {
            flag: sorted(r["root_id"] for r in observations
                         if flag in r["review_flags"])
            for flag in sorted(flagcounts)
        }
    return output


def inspect_original(path: Path, *, include_root_ids: bool = False) -> dict:
    require(path.is_file() and not path.is_symlink(),
            "Expected approved staged original Pass-A file, not symlink")
    require(path.stat().st_size == ORIGINAL_SIZE,
            "Original Pass-A 25,549,416-byte file size mismatch")
    digest = hashlib.sha256()
    observations = []
    with path.open("rb") as stream:
        for n, line in enumerate(stream, start=1):
            digest.update(line)
            try:
                root = json.loads(line.decode("utf-8", errors="strict"))
            except (ValueError, UnicodeError) as e:
                raise OriginalChronologyError(
                    "Original Pass-A JSONL line cannot be decoded at record "
                    + str(n)) from e
            observations.append(one_root(root))
    require(digest.hexdigest() == ORIGINAL_SHA256,
            "Original Pass-A file SHA-256 not the archived exporter digest")
    result = summarize(observations, include_root_ids=include_root_ids)
    result["exact_original_Pass_A_full_bytes_SHA256_verified_now"] = True
    result["source_sha256"] = ORIGINAL_SHA256
    result["source_bytes"] = ORIGINAL_SIZE
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pass-a-jsonl", type=Path, required=True,
                        help="Explicitly staged unmodified original Wits Pass-A JSONL")
    parser.add_argument("--list-flagged", action="store_true",
                        help="Include root IDs (never source issue text) in output")
    args = parser.parse_args(argv)
    print(json.dumps(inspect_original(args.pass_a_jsonl,
                                      include_root_ids=args.list_flagged),
                     sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
