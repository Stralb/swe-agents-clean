"""Fail-closed audit of seven source-linked PR/advisory publication orderings.

Default CI checks private committed provenance/registered external observations.
It does NOT contact public advisory APIs or authenticate Wits D2 packet bytes,
and seven selected findings are NOT the prevalence of post-merge advisories
among the 41 roots, 190 pairs, or 3,809 GitHub workflows.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "provenance" / "seven_postmerge_advisory_publication_cases_20261023.json"
LOCKFILE = BASE / "provenance" / "d_chronology_incomplete_41_lockfile_census_20261023.json"
C1C2 = BASE / "provenance" / "c1_c2_crossfile_readonly_audit_20261022.json"

# Public source-reading evidence and original Wits D2 field values.
EXPECTED = {
    "CROOT-13918-01": (13918, "Pimzino/spec-workflow-mcp", 173,
                       "@babel/core", "7.28.5", "GHSA-4x5r-pxfx-6jf8",
                       "CVE-2026-49356", "2025-12-19T13:54:38Z",
                       "2026-06-13", False),
    "CROOT-13918-36": (13918, "Pimzino/spec-workflow-mcp", 173,
                       "ws", "8.18.3", "GHSA-58qx-3vcg-4xpx",
                       "CVE-2026-45736", "2025-12-19T13:54:38Z",
                       "2026-05-12", False),
    "CROOT-00664-01": (664, "vercel-labs/skills", 135,
                       "rollup", "4.56.0", "GHSA-mw96-cpmx-2vgc",
                       "CVE-2026-27606", "2026-01-27T00:11:48Z",
                       "2026-02-23", True),
    "CROOT-09942-01": (9942, "getgauge/taiko", 2783,
                       "adm-zip", "0.5.17", "GHSA-xcpc-8h2w-3j85",
                       "CVE-2026-39244", "2026-07-07T13:07:56Z",
                       "2026-07-10", True),
    "CROOT-12898-02": (12898, "yagop/node-telegram-bot-api", 1325,
                       "fast-uri", "3.1.2", "GHSA-4c8g-83qw-93j6",
                       "CVE-2026-13676", "2026-06-25T09:28:08Z",
                       "2026-06-29", True),
    "CROOT-12925-01": (12925, "ericblade/quagga2", 664,
                       "systeminformation", "5.29.1", "GHSA-9c88-49p5-5ggf",
                       "CVE-2026-26280", "2026-01-17T21:20:53Z",
                       "2026-02-17", True),
    "CROOT-16311-01": (16311, "less/less.js", 4422,
                       "lodash", "4.17.23", "GHSA-r5fr-rjxr-66jc",
                       "CVE-2026-4800", "2026-03-13T21:40:43Z",
                       "2026-03-31", True),
}


class AdvisoryPublicationError(ValueError):
    """Unsupported original-root provenance, chronology or denominator claim."""


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise AdvisoryPublicationError(msg)


def audit(source: dict | None = None) -> dict:
    x = json.loads(SOURCE.read_text(encoding="utf-8")) if source is None else source
    require(x.get("schema_version") == 1 and x.get("status") ==
            "SEVEN_SOURCE_LINKED_ADVISORY_PUBLICATIONS_POSTDATE_SIX_ORIGINAL_PR_MERGES__CONSERVATIVE_NONEXHAUSTIVE",
            "Unverified seven-observation evidence status")
    evidence = x["source_provenance"]
    require(evidence["D1_root_index_sha256"] ==
            "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3"
            and evidence["D_evidence_index_sha256"] ==
            "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6"
            and evidence["Wits_original_D2_packet_SHA256s_individually_authenticated"] is False,
            "Original Wits D evidence provenance silently promoted/changed")
    denom = x["numerators_and_denominators"]
    require(denom == {
        "seven_concrete_root_advisory_pairs": 7,
        "distinct_source_root_ids": 7,
        "original_export_chronology_incomplete_root_population": 41,
        "distinct_affected_workflows": 6,
        "total_chronology_incomplete_workflows": 6,
        "distinct_original_C2_matched_positive_workflows_in_this_sample": 5,
        "original_C2_matched_pairs": 190,
        "case13918_original_unmatched_positive": True,
        "all_41_root_advisories_exhaustively_checked": False,
        "all_scanner_positive_workflows_in_full_cohort_audited": False,
    }, "Post-merge advisory subset denominator or scope changed")
    flags = x["publication_semantics"]
    require(flags.get("all_7_same_source_advisory_postdates_PR_merge") is True and
            flags.get("date_precision") ==
            "calendar date in UTC; exact advisory publication times are not claimed" and
            flags.get("calendar_day_gap_semantics") ==
            "advisory publication UTC calendar day minus PR merge UTC calendar day; not exact elapsed hours",
            "Advisory timing precision or label drift")
    for key in (
        "specific_advisory_publication_proves_earliest_possible_disclosure",
        "earlier_private_disclosure_or_other_public_warning_excluded",
        "vulnerability_did_not_exist_before_advisory",
        "no_other_preexisting_guidance_existed",
        "scanner_would_have_produced_same_future_CVE_at_PR_time",
        "scanner_warning_at_PR_time_independently_replayed",
        "issue_text_or_agent_prompt_knew_CVE_at_PR_time",
        "scanner_detection_is_exploitability_or_reachability_proof",
        "all_41_advisories_publication_checked",
        "D_final_and_D7_semantic_labels_newly_adjudicated",
        "C1_C2_original_frozen_labels_modified",
    ):
        require(flags.get(key) is False, "Unsupported historical or causal claim: "+key)

    locked = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    require(locked["status"].startswith(
        "SOURCE_IDENTIFIED_41_EXPORT_CHRONOLOGY_INCOMPLETE_ROOTS_"
    ) and locked["population"]["chronology_incomplete_roots"] == 41,
            "Original lockfile 41-root source scope changed")
    single = {r["root_id"]: r for r in locked["other_five_roots"]}
    case13918 = set(locked["case13918"]["all_root_ids"])
    original_c1_c2 = json.loads(C1C2.read_text(encoding="utf-8"))
    require(original_c1_c2["crossfile"]["unmatched_positive_case_ids"] ==
            [13918, 17460] and
            original_c1_c2["c2_accounting"]["matched_pairs"] == 190,
            "Original C2 matched-membership recording changed")

    rows = x["observations"]
    require(isinstance(rows, list) and len(rows) == len(EXPECTED) == 7 and
            {r["root_id"] for r in rows} == set(EXPECTED),
            "Unknown, duplicate or missing audited root/advisory pairing")
    require(len({r["root_id"] for r in rows}) == 7 and
            len({r["ghsa"] for r in rows}) == 7,
            "Duplicated root/advisory identifier")
    all_cases = set()
    matched_cases = set()
    actual_gaps = {}
    for row in rows:
        root = row["root_id"]
        (case, repo, number, pkg, version, ghsa, cve,
         merge, published, matched) = EXPECTED[root]
        fields = (
            row["case_id"], row["repository"], row["pr_number"],
            row["package_name"], row["version"], row["ghsa"],
            row["cve"], row["pr_merged_utc"],
            row["advisory_publication_calendar_date"],
            row["positive_member_of_original_C2_190"],
        )
        require(fields == EXPECTED[root],
                "Original source-identified root, CVE, timing or C2 label drift")
        require(row["pr_url"] == f"https://github.com/{repo}/pull/{number}"
                and row["advisory_url"].startswith("https://github.com/") and
                ghsa.lower() in row["advisory_url"].lower(),
                "GitHub PR/advisory public provenance mismatch")
        require(row["publication_kind"] in (
            "upstream_advisory", "github_advisory_database"),
            "Unverified advisory publication-time source type")
        require(row["post_merge_publication"] is True,
                "Post-merge claim inconsistent with source type")
        require(re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", published) is not None
                and merge.endswith("Z"),
                "Publication calendar date or PR UTC timestamp format invalid")
        dt = datetime.fromisoformat(merge.replace("Z", "+00:00"))
        require(dt.tzinfo is not None and dt.utcoffset().total_seconds() == 0,
                "PR merge timestamp lacks UTC zone")
        day_gap = (date.fromisoformat(published) - dt.date()).days
        require(day_gap > 0 and row["calendar_day_gap_utc"] == day_gap,
                "Advisory not strictly after PR merge or calendar gap inconsistent")
        actual_gaps[root] = day_gap
        require(root in (case13918 if case == 13918 else single),
                "Published advisory root not among original 41 D cases")
        if case != 13918:
            control = single[root]
            require(control["case_id"] == case and
                    control["package"] == pkg and control["version"] == version
                    and control["finding_family"] == "Dependency vulnerability",
                    "Original D2 dependency family/packaging changed")
        require(matched is (case != 13918),
                "Original matched-control membership misunderstood")
        all_cases.add(case)
        if matched:
            matched_cases.add(case)
    require(len(all_cases) == 6 and len(matched_cases) == 5 and
            set(actual_gaps) == set(EXPECTED),
            "Historical workflow-level clustering changed")
    return {
        "status": "PASS_RECORDED_7_PUBLIC_ADVISORY_PR_ORDERINGS_NONEXHAUSTIVE",
        "external_GitHub_API_or_advisory_pages_refetched_in_this_CI": False,
        "Wits_D2_packet_byte_sha_authenticated_in_this_CI": False,
        "all_41_advisory_publications_audited": False,
        "advisory_publications_after_merge_in_registered_sample": 7,
        "distinct_positive_workflows_in_registered_sample": 6,
        "original_matched_positive_workflows_in_registered_sample": 5,
        "original_unmatched_positive_workflows_in_registered_sample": 1,
        "calendar_day_gap_minimum": min(actual_gaps.values()),
        "calendar_day_gap_maximum": max(actual_gaps.values()),
        "prospective_security_warnings_replayed": False,
        "original_C1_C2_D_labels_modified": False,
    }


def main() -> int:
    print(json.dumps(audit(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
