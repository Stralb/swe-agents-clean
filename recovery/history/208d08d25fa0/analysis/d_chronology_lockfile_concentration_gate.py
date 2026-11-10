"""Audit 41 D-export chronology-incomplete roots as source-recorded lockfile PCs.

The original D1 and 342-root export index were SHA-verified through Wits in
a separate live audit. CI's default mode checks a committed derived manifest,
the independent C1/C2 membership ledger and the 43 disputed D labels. It does
NOT reread private source bytes.

To independently replay source evidence, stage both original CSVs outside Git
and supply --d1 and --evidence-index; both exact SHA-256 hashes are mandatory.

This audit does not assign H/T/M, infer T5, declare vulnerabilities, or alter
any original evidence. Multiple roots in one workflow are not iid.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
MANIFEST = BASE / "provenance" / "d_chronology_incomplete_41_lockfile_census_20261023.json"
C1C2 = BASE / "provenance" / "c1_c2_crossfile_readonly_audit_20261022.json"
D_DISPUTES = BASE / "provenance" / "d_vs_d7_label_differences.csv"
D1_SHA = "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3"
DEXPORT_SHA = "cfca8cd2425d7043e89cdb4e06576f3e6794c09736bb5c85b4c0e8332cc3f4e6"
D1_SIZE = 66543
DEXPORT_SIZE = 47826


class LockfileChronologyError(ValueError):
    """Scientific source drift or unsupported classification claim."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LockfileChronologyError(message)


def parse_csv(data: bytes) -> list[dict[str, str]]:
    try:
        stream = io.StringIO(data.decode("utf-8", errors="strict"))
        records = list(csv.DictReader(stream))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise LockfileChronologyError("Malformed source CSV") from exc
    require(all(None not in record for record in records),
            "Unexpected CSV field count")
    return records


def fetch_private_csv(path: Path, size: int, sha256: str) -> list[dict[str, str]]:
    require(path.is_file() and not path.is_symlink(),
            "Private source must be an existing ordinary file, not a symlink")
    require(path.stat().st_size == size, "Original source byte count mismatch")
    with path.open("rb") as stream:
        raw = stream.read(size + 1)
    require(len(raw) == size and hashlib.sha256(raw).hexdigest() == sha256,
            "Original source SHA-256 mismatch")
    return parse_csv(raw)


def audit(
    *,
    supplied_manifest: dict | None = None,
    d1_path: Path | None = None,
    evidence_index_path: Path | None = None,
) -> dict:
    require((d1_path is None) == (evidence_index_path is None),
            "Both original source paths must be supplied together")
    x = (json.loads(MANIFEST.read_text(encoding="utf-8"))
         if supplied_manifest is None else supplied_manifest)
    require(x.get("schema_version") == 1 and
            x.get("status") ==
            "SOURCE_IDENTIFIED_41_EXPORT_CHRONOLOGY_INCOMPLETE_ROOTS_ARE_LOCKFILE_DEPENDENCY_CHANGES__NO_D_ROUTE_ADJUDICATION",
            "Not the source-grounded lockfile census")

    src = x["sources"]
    for key, expected_sha, size in (
        ("d_export_index", DEXPORT_SHA, DEXPORT_SIZE),
        ("d1_root_index", D1_SHA, D1_SIZE),
    ):
        record = src[key]
        require(record.get("sha256") == expected_sha and
                record.get("size_bytes") == size and
                record.get("record_count") == 342 and
                record.get("full_sha256_newly_verified_this_session") is True,
                "Original Wits index provenance changed: " + key)
    c6 = src["c6_original_root_census"]
    require(c6.get("path") ==
            "D_COMPLETE_ROOT_PROVENANCE_v1_0/01_INPUT/C6_ROOT_CENSUS.csv"
            and c6.get("size_bytes") == 179190
            and c6.get("original_sha256_previously_attested") ==
            "97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c"
            and c6.get("full_source_sha256_recomputed_during_current_c6_targeted_read")
            is False and c6.get("case13918_C6_rows_directly_read_from_original") == 36,
            "Source C6 root-census targeted-read provenance changed")
    require(src["remaining_five_d2_packets"]["all_five_read_individually"] is True
            and src["remaining_five_d2_packets"]["all_five_finding_family"]
            == "Dependency vulnerability" and
            src["remaining_five_d2_packets"]["all_five_mechanism_mentions_package_lock"]
            is True, "Five original D2 source-reading provenance changed")
    require(src["original_full_D_final_and_D7_route_CSVs_sha_authenticated"] is False,
            "Invalid claim to original D route labels")
    p = x["population"]
    expected_population = {
        "all_roots": 342, "positive_root_workflows": 191,
        "all_pcs": 455, "original_C1_scanner_positive": 192,
        "original_C2_matched_pairs": 190, "chronology_incomplete_roots": 41,
        "chronology_incomplete_workflows": 6,
        "chronology_incomplete_pcs": 41,
        "chronology_incomplete_dependency_lockfile_roots": 41,
        "lockfile_case13918_roots": 36, "other_cases_roots": 5,
        "unfetched_external_among_41": 3,
        "project_instructions_complete_among_41": 3,
        "disputed_D_final_D7_overlap": 0,
    }
    require(p == expected_population, "Source denominator/missingness changed")

    case = x["case13918"]
    require(case["case_id"] == 13918 and
            case["repository"] == "Pimzino/spec-workflow-mcp" and
            (case["issue_number"], case["pr_number"]) == (172, 173),
            "One-workflow concentration identity changed")
    roots = case["all_root_ids"]
    expected = [f"CROOT-13918-{n:02d}" for n in range(1, 37)]
    require(roots == expected and case["all_root_PC_counts"] == 1 and
            case["all_D1_summaries_contain_package_lock_json"] is True and
            case["original_D1_labels_effective_A"] == "A4" and
            case["original_D1_labels_effective_B"] == "B2" and
            case["these_are_NOT_D0_H_T_M_or_T1_T5_labels"] is True,
            "Original 36 root index/old C labels changed")
    c6_reconstruction = case["C6_root_construction"]
    require(c6_reconstruction.get("root_count") == 36 and
            c6_reconstruction.get("pc_per_root") == 1 and
            c6_reconstruction.get("merge_rationale") == "singleton PC" and
            c6_reconstruction.get("final_source") == "A_B_AGREEMENT" and
            c6_reconstruction.get("all_36_root_summaries_contain_package_lock_json")
            is True and
            c6_reconstruction.get("all_36_subproblems_describe_dependency_resolution_or_version_selection")
            is True, "Original C6 36 singleton-root construction changed")
    require(case["export_chronology"] == "INCOMPLETE" and
            case["external_guidance"] == "NOT_APPLICABLE" and
            case["project_instructions"] == "NOT_APPLICABLE",
            "Original case-13918 evidence-index flags changed")
    require(case["C2_matched_positive_member"] is False and
            case["source_C1_C2_crossfile_unmatched_positive_cases"] == [13918, 17460],
            "Original C1/C2 excluded case changed")
    require(case["github_pr_description_contains_copilot_original_prompt_section"]
            is True and case["substantive_original_bugfix_exists"] is True,
            "Historical PR context changed")
    require(case["changed_files_from_public_PR"] == [
        "package-lock.json", "src/tools/__tests__/projectPath.test.ts",
        "src/tools/approvals.ts",
    ], "Source PR changed-file list changed")
    require(case["public_base_head_file_changes"] == {
        "package_lock": {"additions": 2225, "deletions": 8226, "changes": 10451},
        "tests": {"additions": 49, "deletions": 0, "changes": 49},
        "approvals": {"additions": 24, "deletions": 3, "changes": 27},
    }, "Original public PR base/head file statistics changed")

    c1c2 = json.loads(C1C2.read_text(encoding="utf-8"))
    require(c1c2.get("status") == "PASS_STORED_C1_C2_CROSSFILE_MEMBERSHIP_ONLY"
            and c1c2["crossfile"]["unmatched_positive_case_ids"] == [13918, 17460]
            and c1c2["c2_accounting"]["matched_pairs"] == 190,
            "Frozen C1/C2 original recorded crosswalk is inconsistent")

    singles = x["other_five_roots"]
    expected_singles = {
        664: ("CROOT-00664-01", "rollup", "4.56.0", True),
        9942: ("CROOT-09942-01", "adm-zip", "0.5.17", False),
        12898: ("CROOT-12898-02", "fast-uri", "3.1.2", True),
        12925: ("CROOT-12925-01", "systeminformation", "5.29.1", True),
        16311: ("CROOT-16311-01", "lodash", "4.17.23", False),
    }
    require(len(singles) == 5 and
            {r["case_id"] for r in singles} == set(expected_singles),
            "Five single-root workflow identities changed")
    ids = set(roots)
    for r in singles:
        root, pkg, version, external = expected_singles[r["case_id"]]
        require(r["root_id"] == root and r["root_id"] not in ids and
                r["package"] == pkg and r["version"] == version and
                r["pc_count"] == 1 and r["export_chronology"] == "INCOMPLETE"
                and r["root_mechanism_location"] == "package-lock.json"
                and r["finding_family"] == "Dependency vulnerability"
                and r["external"] ==
                ("URLS_PRESENT_UNFETCHED" if external else "NOT_APPLICABLE")
                and r["original_D_final_route_verified"] is False and
                r["original_D7_route_verified"] is False,
                "Single-root original packet/metadata unexpectedly changed")
        ids.add(root)
    require(len(ids) == 41, "Missing, duplicate or extra chronology-incomplete root")

    drows = parse_csv(D_DISPUTES.read_bytes())
    require(len(drows) == 43 and not ids.intersection(
        {r["root_id"] for r in drows}
    ), "A chronology-incomplete root appears in the frozen D/D7 disputed set")

    require(x["limitations"].get(
        "C6_root_group_agreement_proves_independent_agent_mechanism_choices"
    ) is False, "Misreported original C6 root grouping as agent-choice reliability")
    for key in (
        "all_41_D_semantic_routes_reproduced",
        "all_41_vulnerability_truth_fully_reproduced",
        "all_41_dependencies_proven_to_be_resolver_generated",
        "one_lockfile_change_is_one_vulnerability",
        "unmatched_positive_case13918_impacts_frozen_C2_statistics",
        "mechanical_root_labels_adjudicated",
        "root_level_and_workflow_level_observations_iid",
    ):
        require(x["limitations"].get(key) is False,
                "Unsupported H/T/M, scanner or independence claim: "+key)
    require(all(v is True for v in x["proposed_scientific_handling"].values()),
            "Scientific handling restrictions changed")

    staged = d1_path is not None
    if staged:
        d1 = fetch_private_csv(d1_path, D1_SIZE, D1_SHA)
        index = fetch_private_csv(evidence_index_path, DEXPORT_SIZE, DEXPORT_SHA)
        require(len(d1) == len(index) == 342,
                "Original D1/export source denominator changed")
        d1map = {r["Root ID"]: r for r in d1}
        ixmap = {r["root_id"]: r for r in index}
        require(len(d1map) == len(ixmap) == 342 and
                set(d1map) == set(ixmap),
                "D1/root-export membership mismatch")
        require(sum(r["channel_chronology"] == "INCOMPLETE" for r in index) == 41,
                "Original export chronology count changed")
        require({r["root_id"] for r in index
                 if r["channel_chronology"] == "INCOMPLETE"} == ids,
                "Exact list of 41 incomplete-source roots changed")
        for root in ids:
            a, b = d1map[root], ixmap[root]
            require("package-lock.json" in a["Root Summary"] and
                    "version" in a["Root Summary"].lower() and
                    a["PC Count"] == b["pc_count"] == "1" and
                    a["Case ID"] == b["case_id"],
                    "One original chronology-incomplete root is not a "
                    "single-producing-change package-lock version entry")
        for root in roots:
            a = d1map[root]
            require(a["Effective A Labels Present"] == "A4" and
                    a["Effective B Labels Present"] == "B2",
                    "Old C-era A/B labels changed for workflow 13918")

    return {
        "status": ("PASS_SHA256_ORIGINAL_D1_EXPORT_ALL_41_LOCKFILE_ROOTS"
                   if staged else "PASS_RECORDED_41_LOCKFILE_ROOTS_RECONCILIATION"),
        "original_D1_and_export_index_bytes_SHA_checked_in_this_execution": staged,
        "frozen_original_H_T_M_labels_authenticated": False,
        "semantic_T_routes_adjudicated": False,
        "chronology_incomplete_export_roots": 41,
        "chronology_incomplete_root_workflows": 6,
        "case13918_lockfile_roots": 36,
        "case13918_in_190_original_positive_matched_members": False,
        "other_five_lockfile_roots": 5,
        "frozen_D_final_D7_disagreement_overlap": 0,
        "unfetched_external_root_count": 3,
        "root_producing_change_count_for_41": 41,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d1", type=Path, help="Original private D1_ROOT_INDEX_342.csv")
    parser.add_argument("--evidence-index", type=Path,
                        help="Original private D_EVIDENCE_INDEX_342.csv")
    args = parser.parse_args(argv)
    if (args.d1 is None) != (args.evidence_index is None):
        parser.error("Supply both --d1 and --evidence-index, or neither")
    print(json.dumps(
        audit(d1_path=args.d1, evidence_index_path=args.evidence_index),
        sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
