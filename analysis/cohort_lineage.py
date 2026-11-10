"""Fail-closed source-recorded lineage audit and optional local C1/C2 CSV replay.

The committed JSON records *aggregate observations made via Wits read-only
tools*, not frozen row-level inputs or a claim of independent reproduction.
The optional local file command independently verifies separately provided
original C1 and C2 CSV bytes against pre-established frozen SHA-256 digests
and replays membership/tier relations without generating new controls.

No network, scanner calls, shell commands, data copying or file writes.
Neither command executes historical scripts or opens a production SQLite DB.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]
LINEAGE_FILE = ROOT / "data" / "cohort_lineage.json"
MAX_STAGED_BYTES = 16 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class StageEvidenceError(ValueError):
    """A frozen aggregate or an optional candidate CSV violated a gate."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise StageEvidenceError(message)


def load_recorded(path: Path = LINEAGE_FILE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and data.get("schema_version") == 1,
            "Unsupported recorded stage ledger version")
    require(data.get("status") == "SOURCE_RECORDED_STAGE_RELATIONS_ONLY",
            "Recorded summary cannot be promoted to historical reproduction")
    return data


def audit_recorded(data: dict) -> dict:
    """Cross-check observed aggregates; NEVER claim rederived row-level units."""
    x = data["final_discovery_database"]
    snapshots = data["intermediate_readonly_sql"]["snapshots"]
    c1 = data["c1_scanner_opportunity"]
    c2 = data["c2_matching"]
    pc = data["phase1_producing_change_population"]
    roots = data["c_root_census"]
    scope = data["scope"]

    for digest in (
        x["archived_source_and_manifest_expected_sha256"],
        c1["input_sha256"], c1["positive_ids_sha256_reported"],
        c1["db_sha256_reported"], c2["input_c1_expected_sha256"],
        c2["matched_pairs_sha256"], pc["frozen_455_provenance_sha256_reported"],
    ):
        require(isinstance(digest, str) and bool(HEX64.fullmatch(digest)),
                "Missing/invalid original SHA-256 fingerprint")
    require(
        x["archived_source_and_manifest_expected_sha256"] ==
        c1["db_sha256_reported"] ==
        "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa",
        "Independent archive/cluster declared final snapshot hashes disagree",
    )
    require(c1["input_sha256"] == c2["input_c1_expected_sha256"] ==
            "6028cb41a3ab80921395f16ffd7c398763631d901363a4a326cb5f04bdca5d7b",
            "C1-to-C2 frozen input digest mismatch")
    require(c1["input_bytes"] == 841710 and
            c2["matched_pairs_bytes"] == 56175,
            "Frozen CSV size metadata changed")
    require(len(snapshots) == 2, "Expected two separately dated intermediate DBs")
    intermediate = {}
    for snapshot in snapshots:
        label = snapshot["label"]
        states = snapshot["states"]
        require(label not in intermediate and
                snapshot["cases"] == 3809 and
                sum(states.values()) == snapshot["cases"] and
                all(type(n) is int and n >= 0 for n in states.values()),
                "Invalid intermediate case-stage partition")
        require(set(states) == {
            "scan_blocked", "scanner_running", "scanned_clean", "needs_review"
        }, "Unexpected intermediate scanner-stage category")
        require(snapshot["sha256_verified"] is False,
                "Intermediate snapshot hash falsely attested")
        intermediate[label] = states["needs_review"]
    require(intermediate == {
        "2026-08-17-hf-snapshot": 138,
        "2026-08-21-continuation": 198,
    }, "Recorded intermediate status counts changed")
    require(x["source_reported_cases"] == 3809 and
            x["source_reported_repositories"] == 723 and
            x["source_reported_pr_file_rows"] == 31223,
            "Final discovery run manifest aggregate mismatch")
    require(x["final_database_bytes_independently_hashed"] is False and
            x["huggingface_private_revision_verified"] is False,
            "Final database/HF provenance was promoted without independent proof")

    require(c1["cases"] == 3809 and c1["positives"] == 192 and
            c1["potential_negatives"] == 3617 and
            c1["positives"] + c1["potential_negatives"] == c1["cases"],
            "Scanner-opportunity C1 population partition broken")
    require(c1["same_repo_superset_possible"] == 150 and
            c1["same_repo_superset_unavailable"] == 42 and
            c1["same_repo_superset_possible"] +
            c1["same_repo_superset_unavailable"] == c1["positives"],
            "C1 same-repository feasibility partition broken")
    require(c1["any_repo_exact_possible"] == c1["positives"] and
            c1["complete_opportunity_positive_with_empty"] == 0,
            "C1 original negative-opportunity feasibility changed")
    require(set(c1["paired_instrument_families"]) ==
            {"codeql", "osv", "trivy"} and
            set(c1["single_stage_families"]) ==
            {"dependency_diff", "gitleaks", "semgrep"},
            "Original scanner-success family normalization changed")
    require(c1["source_reported_success_statuses"] ==
            ["complete", "completed", "finding", "ok"],
            "Frozen scanner-success status list changed")
    require(c1["source_selected_controls"] is False and
            c1["source_audit_db_hash_match_reported"] is True and
            c1["source_audit_input_current_bytes_not_reverified"] is True,
            "C1 source-reporting versus verification boundary altered")
    require(c2["positive_cases"] == c1["positives"] and
            c2["matched_pairs"] == 190 and
            c2["unmatched_positive_count"] == 2 and
            c2["matched_pairs"] + c2["unmatched_positive_count"] ==
            c2["positive_cases"], "C2 matched-positive denominator changed")
    require(c2["same_repo_tier_a"] == 115 and
            c2["cross_repo_tier_b"] == 75 and
            c2["same_repo_tier_a"] + c2["cross_repo_tier_b"] ==
            c2["matched_pairs"], "Frozen C2 matching-tier sum invalid")
    require(c2["seed"] == 20260903 and
            c2["time_caliper_days"] == 90 and
            c2["controls_selected_without_replacement"] is True and
            c2["substantive_outcomes_compared"] is False,
            "C2 selection or no-outcomes condition changed")

    require(pc["producing_changes"] == 455 and
            pc["eligible_cases"] == 191 and
            pc["pilot_context_records"] == 160 and
            pc["scaleout_context_records"] == 295 and
            pc["matched_context_records"] == 455 and
            pc["pilot_context_records"] + pc["scaleout_context_records"] ==
            pc["matched_context_records"], "Phase1 producing-change crosswalk changed")
    require(pc["phase1_status"] == "REVIEW_REQUIRED" and
            pc["validity_labels_predefined_but_not_fully_adjudicated"] is True,
            "Phase1 validity status prematurely promoted")
    require(pc["introduction_status"] == {"resolved": 414, "unresolved": 41} and
            sum(pc["introduction_status"].values()) == 455,
            "Introduction-status partial-resolution ledger changed")
    require(pc["finding_family"] == {
        "Code vulnerability": 261,
        "Dependency vulnerability": 96,
        "Dependency downgrade": 64,
        "Secret exposure": 26,
        "Dependency change": 8,
    } and sum(pc["finding_family"].values()) == 455,
        "Phase1 source-recorded finding-family totals changed")
    require(pc["path_role_hint"] == {
        "runtime/other": 178,
        "dependency/lockfile": 168,
        "test/fixture": 107,
        "documentation": 2,
    } and sum(pc["path_role_hint"].values()) == 455,
        "Phase1 source-recorded path-role totals changed")

    dist = roots["root_size_distribution"]
    count = sum(int(size) * amount for size, amount in dist.items())
    root_count = sum(dist.values())
    require(roots["root_audit_status"] == "PASS" and
            roots["producing_changes"] == count == 455 and
            roots["distinct_roots"] == root_count == 342 and
            roots["mapped_workflows"] == pc["eligible_cases"] == 191,
            "C/D root size distribution or workflow count inconsistent")
    require(dist == {
        "1": 283, "2": 36, "3": 9, "4": 7,
        "5": 3, "6": 3, "12": 1,
    } and roots["duplicate_pc_assignments"] ==
            roots["cross_workflow_roots"] ==
            roots["root_count_mismatches"] == 0,
            "Frozen independent root assignment audit disagrees")

    for key in (
        "final_discovery_sqlite_bytes_currently_rehashed",
        "c1_c2_csv_bytes_currently_rehashed",
        "independent_final_positive_set_reconstructed",
        "independent_455_pc_membership_reconstructed",
        "independent_342_root_assignments_reconstructed",
        "observational_causal_claim_justified",
        "sensitive_row_level_data_committed",
    ):
        require(scope[key] is False, f"Premature provenance/scientific promotion: {key}")
    require(scope["recorded_summary_arithmetic_verified_only"] is True,
            "Recorded arithmetic scope mislabeled")
    return {
        "status": "PASS_RECORDED_C1_C2_PHASE1_C_ROOT_ARITHMETIC_ONLY",
        "source_declared_final_db_sha256":
            x["archived_source_and_manifest_expected_sha256"],
        "intermediate_needs_review": intermediate,
        "final_c1_cases": c1["cases"],
        "final_c1_positive_cases_source_reported": c1["positives"],
        "final_c1_negative_pool_source_reported": c1["potential_negatives"],
        "frozen_c2_pairs_source_reported": c2["matched_pairs"],
        "frozen_c2_same_repo_pairs": c2["same_repo_tier_a"],
        "frozen_c2_cross_repo_pairs": c2["cross_repo_tier_b"],
        "phase1_changes_source_reported": pc["producing_changes"],
        "phase1_workflows_source_reported": pc["eligible_cases"],
        "phase1_introduction_status": pc["introduction_status"],
        "root_count_source_reported": roots["distinct_roots"],
        "root_distribution_size_weighted_sum": count,
        "c1_c2_csv_source_files_rehashed": False,
        "final_sqlite_bytes_independently_verified": False,
        "empirical_security_results_reproduced": False,
        "note": "Recorded aggregate arithmetic and previous read-only SQL "
                "are not independent recreation of final cohorts or security warnings.",
    }


def _regular_staged(path: Path, expected_size: int, label: str) -> tuple[Path, tuple]:
    path = path.absolute()
    require(ROOT != path and ROOT not in path.parents,
            f"{label} cannot be staged inside this Git checkout")
    for member in (path, *path.parents):
        require(not member.is_symlink(), f"{label} contains a symlink")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
            f"Missing/nonregular staged {label}")
    st = path.stat()
    require(st.st_size == expected_size and
            0 < st.st_size <= MAX_STAGED_BYTES,
            f"Frozen staged {label} byte size mismatch")
    return path, (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _csv_rows(path: Path, digest: str, expected_size: int,
              required_columns: set[str], label: str) -> list[dict[str, str]]:
    path, stat_before = _regular_staged(path, expected_size, label)
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == digest,
            f"{label} SHA-256 differs from frozen source file inventory")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames is not None and
                required_columns <= set(reader.fieldnames),
                f"Missing {label} frozen CSV columns")
        rows = list(reader)
    st = path.stat()
    require((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
            == stat_before, f"{label} changed during read")
    require(rows and all(None not in row and
            all(value is not None for value in row.values())
            for row in rows), f"{label} has malformed rows")
    return rows


def verify_local_c1_c2(c1_path: Path, c2_path: Path,
                       data: dict, *, expected_counts: tuple[int,int,int,int]
                       | None = None) -> dict:
    """Local byte-verified study selections; input files never entered into Git.

    expected_counts customization exists for synthetic in-memory tests only.
    The public CLI always uses the source-recorded 3,809/192/190/115 counts.
    """
    c1_meta, c2_meta = data["c1_scanner_opportunity"], data["c2_matching"]
    exp_cases, exp_pos, exp_pairs, exp_same = (
        expected_counts if expected_counts is not None
        else (3809, 192, 190, 115)
    )
    c1 = _csv_rows(
        c1_path, c1_meta["input_sha256"], c1_meta["input_bytes"],
        {"case_id","is_positive","repository","complete_opportunity_signature"},
        "C1 scanner-opportunity",
    )
    indexed = {}
    for row in c1:
        identifier = row["case_id"]
        require(identifier.isdecimal() and identifier not in indexed,
                "C1 duplicate or malformed case identifier")
        require(row["is_positive"] in ("0", "1"),
                "C1 nonbinary positive label")
        if row["is_positive"] == "1":
            require(bool(row["complete_opportunity_signature"].strip()),
                    "C1 positive has no complete scanner opportunity")
        indexed[identifier] = row
    positives = {id for id,row in indexed.items() if row["is_positive"] == "1"}
    require(len(indexed) == exp_cases and len(positives) == exp_pos,
            "C1 verified input membership count differs from original cohort")
    c2 = _csv_rows(
        c2_path, c2_meta["matched_pairs_sha256"], c2_meta["matched_pairs_bytes"],
        {"positive_case_id", "control_case_id", "match_tier",
         "same_repository", "positive_repository", "control_repository",
         "opportunity_relation","positive_opportunity_signature",
         "control_opportunity_signature","abs_pr_time_days"},
        "C2 matched-control",
    )
    seen_positives, seen_controls, tiers = set(), set(), {"A":0, "B":0}
    for row in c2:
        p, c = row["positive_case_id"], row["control_case_id"]
        require(p in positives and c in indexed and
                indexed[c]["is_positive"] == "0",
                "C2 pair contains nonpositive or nonnegative member")
        require(p not in seen_positives and c not in seen_controls,
                "C2 reused a positive or control")
        seen_positives.add(p)
        seen_controls.add(c)
        tier = row["match_tier"]
        require(tier in tiers, "Unknown C2 matching tier")
        tiers[tier] += 1
        same = row["positive_repository"] == row["control_repository"]
        require(row["positive_repository"] ==
                indexed[p]["repository"] and
                row["control_repository"] ==
                indexed[c]["repository"],
                "C2 matching repository differs from frozen C1 membership")
        require(row["same_repository"] == ("1" if same else "0"),
                "C2 same_repository bit contradicts literal repository")
        sig_p = set(row["positive_opportunity_signature"].split(";"))
        sig_c = set(row["control_opportunity_signature"].split(";"))
        require(sig_p == set(indexed[p]["complete_opportunity_signature"].split(";"))
                and sig_c == set(indexed[c]["complete_opportunity_signature"].split(";")),
                "C2 scanner opportunity differs from C1 frozen input")
        if tier == "A":
            require(same and sig_p <= sig_c,
                    "Tier A must be same-repository with opportunity superset")
        else:
            require(not same and sig_p == sig_c,
                    "Tier B must be cross-repository with exact opportunity")
        try:
            days = float(row["abs_pr_time_days"])
        except (TypeError, ValueError) as exc:
            raise StageEvidenceError("Malformed frozen C2 time delta") from exc
        require(0 <= days <= 90.00001,
                "C2 pair violates frozen ninety-day time caliper")
    require(len(c2) == exp_pairs and tiers["A"] == exp_same and
            tiers["B"] == exp_pairs - exp_same and
            len(seen_controls) == exp_pairs,
            "Frozen matched pair/tier uniqueness count changed")
    return {
        "status": "PASS_BYTE_VERIFIED_STAGED_C1_C2_PAIR_MEMBERSHIP_ONLY",
        "c1_cases": len(indexed), "c1_positive_cases": len(positives),
        "c2_pairs": len(c2), "c2_same_repo_pairs": tiers["A"],
        "c2_cross_repo_pairs": tiers["B"],
        "unmatched_positive_count": len(positives - seen_positives),
        "source_c1_sha256_verified": True,
        "source_c2_sha256_verified": True,
        "reran_original_matching_optimizer": False,
        "ran_historical_scanners": False,
        "read_original_final_sqlite": False,
        "regenerated_root_assignments": False,
        "verified_study_security_outcomes": False,
        "note": "Verifies frozen C1/C2 CSV bytes and existing pairing relationships, "
                "not original matcher optimality or final scanner-positive causality.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("audit-recorded", help="Aggregate/ledger arithmetic only")
    verify = sub.add_parser("verify-staged-c1-c2",
                            help="Verify separately staged private C1/C2 CSV copies")
    verify.add_argument("c1_path", type=Path)
    verify.add_argument("c2_path", type=Path)
    args = parser.parse_args(argv)
    try:
        data = load_recorded()
        audit_recorded(data)
        if args.action == "audit-recorded":
            output = audit_recorded(data)
        else:
            output = verify_local_c1_c2(args.c1_path, args.c2_path, data)
        status = 0
    except (StageEvidenceError, OSError, ValueError, TypeError, KeyError,
            json.JSONDecodeError, csv.Error) as exc:
        output = {
            "status": "BLOCKED_STAGE_PROVENANCE_OR_INPUT",
            "error": str(exc),
            "independent_study_reproduction": False,
        }
        status = 2
    print(json.dumps(output, sort_keys=True, indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
