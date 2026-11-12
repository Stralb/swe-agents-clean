"""Read-only, fail-closed audit of *recorded* research provenance.

This is not a rerun of the historical miner, CodeQL, counterfactual patch
generation, or statistical inference. It validates the supplied, committed
summary ledgers and can hash-verify separately recovered baseline SARIF files.
No network, subprocess, extraction, writes, or Wits access.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGING_NAME = "CASE_{case_id}_before.sarif"
MAX_BASELINE_BYTES = 128 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
ID5 = re.compile(r"[0-9]{5}\Z")

class EvidenceError(ValueError):
    """Recorded evidence does not satisfy an explicitly checked invariant."""


def _rows(path: Path, columns: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or not columns.issubset(set(reader.fieldnames)):
            raise EvidenceError(f"Missing required columns: {path.name}")
        result = list(reader)
    if not result or any(None in row for row in result):
        raise EvidenceError(f"Missing/malformed CSV records: {path.name}")
    return result


def _unique(rows: list[dict[str, str]], field: str) -> set[str]:
    ids = [row[field] for row in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise EvidenceError(f"Missing/duplicate {field}")
    return set(ids)


def _boolean(value: str, label: str) -> bool:
    if value not in ("True", "False"):
        raise EvidenceError(f"Unexpected {label} Boolean: {value!r}")
    return value == "True"


def _count(value: str, label: str) -> int | None:
    if value == "NOT_UPLOADED":
        return None
    if not re.fullmatch(r"[0-9]+", value):
        raise EvidenceError(f"Unexpected {label} count: {value!r}")
    return int(value)


def _required(condition: bool, description: str) -> None:
    if not condition:
        raise EvidenceError(description)


def read_baseline_inventory(path: Path) -> list[dict[str, str]]:
    required = {
        "case_id", "expected_before_sarif_sha256",
        "source_reported_before_results", "codeql_version",
        "O_source_archive_sha256", "W_source_archive_sha256",
        "P_source_archive_sha256", "baseline_SARIF_available_in_input_zip",
        "source_content_equivalence_independently_verified",
    }
    rows = _rows(path, required)
    _unique(rows, "case_id")
    for row in rows:
        case = row["case_id"]
        _required(bool(ID5.fullmatch(case)), f"Invalid baseline case ID {case!r}")
        _required(bool(HEX64.fullmatch(row["expected_before_sarif_sha256"])),
                  f"Invalid baseline digest {case}")
        _count(row["source_reported_before_results"], f"{case} before results")
        _required(row["baseline_SARIF_available_in_input_zip"] == "NO",
                  f"Unexpected baseline presence claim {case}")
        _required(row["source_content_equivalence_independently_verified"] == "NO",
                  f"Unexpected independent source-equivalence claim {case}")
        for arm in "OWP":
            token = row[f"{arm}_source_archive_sha256"]
            _required(token == "NOT_UPLOADED" or bool(HEX64.fullmatch(token)),
                      f"Invalid {arm} source hash for {case}")
        _required(bool(row["codeql_version"]), f"Missing reported CodeQL version {case}")
    _required(len({r["expected_before_sarif_sha256"] for r in rows}) == len(rows),
              "Baseline inventory contains duplicate digests")
    return rows


def replay_recorded_owp14(provenance: Path) -> dict:
    """Recompute only recorded summary arithmetic, not independent SARIF deltas."""
    cases = _rows(provenance / "owp14_case_arm_counts_20261020.csv", {
        "case_id", "snapshot", "previous_O_target_reproduced",
        "O_new_claimed", "O_target_new_claimed", "W_new_claimed",
        "W_target_new_claimed", "P_new_claimed", "P_target_new_claimed",
        "O_syntax_JSX", "W_syntax_JSX", "P_syntax_JSX",
    })
    ids = _unique(cases, "case_id")
    _required(len(cases) == 14 and all(ID5.fullmatch(x) for x in ids),
              "Expected exactly fourteen distinct five-digit O/W/P case IDs")
    inventory = read_baseline_inventory(
        provenance / "owp14_missing_baseline_sha256.csv"
    )
    _required(set(row["case_id"] for row in inventory) == ids,
              "O/W/P case IDs do not match baseline inventory")
    baselines = {row["case_id"]: row for row in inventory}
    with (provenance / "owp14_intake_verified_20261020.json").open(
        encoding="utf-8"
    ) as stream:
        intake = json.load(stream)
    _required(isinstance(intake, dict) and
              intake.get("scientific_validity") ==
              "EXPLORATORY_ONLY_NOT_INDEPENDENT_ALERT_DELTA_OR_FUNCTIONAL_REPLICATION",
              "Unexpected intake scientific-validity declaration")

    scans: Counter[str] = Counter()
    reported_new: Counter[str] = Counter()
    reported_target: Counter[str] = Counter()
    source_modes: Counter[str] = Counter()
    syntax: Counter[str] = Counter()
    historical_target = 0
    paired = []
    missing_o = []
    full_paired = 0
    for row in cases:
        cid = row["case_id"]
        mode = row["snapshot"]
        _required(mode in ("FULL_FROZEN_SNAPSHOT", "FILTERED_SOURCE_PROVISIONAL"),
                  f"Unexpected source mode {cid}")
        source_modes[mode] += 1
        historical_target += _boolean(
            row["previous_O_target_reproduced"], f"{cid} prior target"
        )
        count_by_arm = {}
        for arm in "OWP":
            n = _count(row[f"{arm}_new_claimed"], f"{cid} {arm} new")
            t = _count(row[f"{arm}_target_new_claimed"], f"{cid} {arm} target")
            label = row[f"{arm}_syntax_JSX"]
            if n is None or t is None:
                _required(n is None and t is None and label == "NOT_UPLOADED",
                          f"Missing arm not consistently marked {cid} {arm}")
                _required(baselines[cid][f"{arm}_source_archive_sha256"] ==
                          "NOT_UPLOADED", f"Missing arm has purported source hash {cid} {arm}")
            else:
                _required(0 <= t <= n, f"Impossible reported target count {cid} {arm}")
                _required(label in ("SYNTAX_PASS", "SYNTAX_FAIL"),
                          f"Missing recorded JSX syntax outcome {cid} {arm}")
                _required(bool(HEX64.fullmatch(
                    baselines[cid][f"{arm}_source_archive_sha256"]
                )), f"Missing source hash for recorded {cid} {arm}")
                scans[arm] += 1
                reported_new[arm] += n
                reported_target[arm] += t
                syntax[label] += 1
            count_by_arm[arm] = n
        if count_by_arm["O"] is None:
            _required(count_by_arm["W"] is not None and
                      count_by_arm["P"] is not None,
                      f"Unpaired case missing W/P {cid}")
            missing_o.append(cid)
        else:
            _required(count_by_arm["W"] is not None and
                      count_by_arm["P"] is not None,
                      f"Paired case missing W/P {cid}")
            paired.append(count_by_arm)
            full_paired += mode == "FULL_FROZEN_SNAPSHOT"
    _required(len(paired) == 12 and len(missing_o) == 2,
              "Historical paired-case denominator changed")
    _required(len({r["codeql_version"] for r in inventory}) == 1,
              "Multiple recorded CodeQL versions across baseline rows")
    metadata = intake.get("scanner", {})
    _required(len(cases) == metadata.get("cases"), "Intake case count conflict")
    for arm in "OWP":
        for suffix, actual in (
            ("scans", scans[arm]), ("new_claimed", reported_new[arm]),
            ("target_claimed", reported_target[arm]),
        ):
            _required(metadata.get("arm_counts", {}).get(f"{arm}_{suffix}") == actual,
                      f"Recorded scanner aggregate conflicts: {arm}_{suffix}")
    _required(dict(source_modes) == metadata.get("source_mode_counts"),
              "Source snapshot mode counts contradict intake")
    _required(historical_target == metadata.get(
        "historical_target_previously_reproduced"
    ), "Previously reproduced target count contradicts intake")
    _required(len(paired) == metadata.get("paired_O_W_P_cases"),
              "Intake reported paired denominator conflict")
    _required([int(x) for x in missing_o] == metadata.get("missing_O_cases"),
              "Missing-O cases contradict intake")
    _required(metadata.get("baseline_SARIF_exported") is False,
              "Intake no longer declares missing baseline SARIF")
    _required(metadata.get("source_reported_full_functional_acceptance") is False,
              "Unreviewed function acceptance has been promoted")
    _required(metadata.get("source_reported_provenance_verified") is False,
              "Unverified provenance has been promoted")
    _required(metadata.get("source_reported_generation_comparability") is False,
              "Unverified generation comparison has been promoted")
    _required(syntax["SYNTAX_PASS"] ==
              intake.get("functional", {}).get("JSX_aware_syntax", {}).get("pass"),
              "Recorded JSX-aware syntax pass count changed")
    _required(sum(syntax.values()) ==
              intake.get("functional", {}).get("JSX_aware_syntax", {}).get("count"),
              "Recorded JSX-aware syntax denominator changed")
    comparisons = {}
    for arm in ("W", "P"):
        comparisons[arm] = {
            "fewer_recorded_new_alerts": sum(p[arm] < p["O"] for p in paired),
            "equal_recorded_new_alerts": sum(p[arm] == p["O"] for p in paired),
            "more_recorded_new_alerts": sum(p[arm] > p["O"] for p in paired),
        }
    _required(comparisons == {
        "W": {"fewer_recorded_new_alerts": 7, "equal_recorded_new_alerts": 5,
              "more_recorded_new_alerts": 0},
        "P": {"fewer_recorded_new_alerts": 4, "equal_recorded_new_alerts": 8,
              "more_recorded_new_alerts": 0},
    }, "Recorded paired descriptive contrasts have changed")
    _required(full_paired == 8,
              "Eight fully frozen, paired cases expected")
    _required(len(inventory) == 14 and
              all(r["baseline_SARIF_available_in_input_zip"] == "NO"
                  for r in inventory),
              "Baseline SARIF inventory differs from 14 missing entries")
    return {
        "status": "PASS_RECORDED_SUMMARY_ARITHMETIC_ONLY",
        "independent_new_alert_delta_verified": False,
        "historical_codeql_version_as_recorded": inventory[0]["codeql_version"],
        "cases": len(cases), "paired_cases": len(paired),
        "paired_full_frozen_cases": full_paired,
        "unpaired_missing_O_cases": missing_o,
        "original_baseline_sarif_missing": len(inventory),
        "scans_by_arm": dict(scans),
        "reported_new_alerts_by_arm": dict(reported_new),
        "reported_new_target_alerts_by_arm": dict(reported_target),
        "recorded_source_modes": dict(source_modes),
        "previously_reproduced_historical_target": historical_target,
        "recorded_jsx_aware_syntax": dict(syntax),
        "recorded_paired_descriptive_contrasts": comparisons,
        "limitations": [
            "Original before-SARIF absent; cannot recompute introduced-warning set differences.",
            "Reported syntax is not full functional or issue acceptance.",
            "Four cases have filtered provisional source snapshots; two have no O arm.",
            "Different per-arm source archive hashes lack content-level equivalence check.",
            "These are recorded descriptive contrasts, not causal intervention effects.",
        ],
    }


def audit_d_d7_ledger(provenance: Path) -> dict:
    rows = _rows(provenance / "d_vs_d7_label_differences.csv", {
        "root_id", "d_final_route", "d_final_tier", "d7_route",
        "d7_tier", "disposition",
    })
    ids = _unique(rows, "root_id")
    _required(len(rows) == 43, "Expected 43 frozen conflicting roots")
    _required(all(r["disposition"] == "UNRESOLVED" for r in rows),
              "Dispute marked adjudicated without frozen decision")
    _required(all(
        (r["d_final_route"], r["d_final_tier"]) !=
        (r["d7_route"], r["d7_tier"])
        for r in rows
    ), "Difference ledger contains an identical route/tier label")
    routes = [r for r in rows if r["d_final_route"] != r["d7_route"]]
    _required(len(routes) == 1 and routes[0]["root_id"] == "CROOT-00649-01",
              "Route reroute changed from frozen conflict ledger")
    _required(
        (routes[0]["d_final_route"], routes[0]["d7_route"]) == ("M", "H"),
        "Expected unresolved original M -> D7 H reroute",
    )
    return {
        "status": "UNRESOLVED_D_VS_D7",
        "changed_root_labels": len(ids),
        "route_changes": len(routes),
        "tier_changes": sum(r["d_final_tier"] != r["d7_tier"] for r in rows),
        "tier_only_changes": sum(
            r["d_final_route"] == r["d7_route"] and
            r["d_final_tier"] != r["d7_tier"] for r in rows
        ),
        "route_changed_root_ids": [r["root_id"] for r in routes],
        "note": "Ledger disagreement verified, labels deliberately not reconciled.",
    }


def verify_staged_baselines(
    inventory: list[dict[str, str]], directory: Path,
    *, max_bytes: int = MAX_BASELINE_BYTES,
) -> dict:
    """Hash and structurally verify staged baselines without touching their bytes.

    Staging names are local-only: CASE_<five-digit-id>_before.sarif.
    They are NOT asserted to be the original archive's file names.
    """
    _required(max_bytes > 0, "Invalid maximum SARIF byte size")
    if directory.exists() and (not directory.is_dir() or directory.is_symlink()):
        raise EvidenceError("Baseline staging root must be a real directory")
    statuses = []
    for row in inventory:
        case = row["case_id"]
        _required(bool(ID5.fullmatch(case)), "Invalid staged case ID")
        path = directory / STAGING_NAME.format(case_id=case)
        item = {"case_id": case, "staging_file": path.name}
        if path.is_symlink():
            item["status"] = "REJECTED_SYMLINK"
        elif not path.is_file():
            item["status"] = "MISSING"
        elif path.stat().st_size > max_bytes:
            item["status"] = "REJECTED_SIZE_LIMIT"
        else:
            body = path.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            if digest != row["expected_before_sarif_sha256"]:
                item["status"] = "HASH_MISMATCH"
            else:
                try:
                    report = json.loads(body)
                    runs = report["runs"]
                    if not isinstance(runs, list) or not runs:
                        raise ValueError("Missing SARIF runs")
                    count = 0
                    for run in runs:
                        results = run["results"]
                        if not isinstance(results, list):
                            raise ValueError("Missing SARIF result list")
                        count += len(results)
                    expected = _count(
                        row["source_reported_before_results"], "before result count"
                    )
                    item["status"] = (
                        "HASH_AND_COUNT_VERIFIED" if count == expected
                        else "RESULT_COUNT_MISMATCH"
                    )
                except (ValueError, TypeError, KeyError, IndexError):
                    item["status"] = "INVALID_SARIF"
        statuses.append(item)
    counts = dict(sorted(Counter(item["status"] for item in statuses).items()))
    complete = len(statuses) == sum(
        item["status"] == "HASH_AND_COUNT_VERIFIED" for item in statuses
    )
    return {
        "status": (
            "ALL_STAGED_BASELINES_HASH_AND_COUNT_VERIFIED" if complete
            else "BLOCKED_MISSING_OR_INVALID_BASELINES"
        ),
        "verified": sum(item["status"] == "HASH_AND_COUNT_VERIFIED" for item in statuses),
        "expected": len(statuses), "counts": counts, "cases": statuses,
        "independent_new_alert_delta_verified": False,
        "note": "Baseline SHA+count alone does not reproduce after/before finding delta.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit-recorded", help="Audit committed summary arithmetic")
    audit.add_argument("--provenance", type=Path, default=ROOT / "provenance")
    verify = sub.add_parser("verify-baselines", help="Check local, read-only SARIF copies")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--provenance", type=Path, default=ROOT / "provenance")
    args = parser.parse_args(argv)
    try:
        if args.command == "audit-recorded":
            report = {
                "OWP14": replay_recorded_owp14(args.provenance),
                "D_D7": audit_d_d7_ledger(args.provenance),
                "scientific_parity": "BLOCKED_ORIGINAL_DATA_NOT_PRESENT",
            }
            status = 0
        else:
            inventory = read_baseline_inventory(
                args.provenance / "owp14_missing_baseline_sha256.csv"
            )
            _required(len(inventory) == 14, "Expected fourteen baseline identifiers")
            report = verify_staged_baselines(inventory, args.directory)
            status = 0 if report["verified"] == report["expected"] else 2
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID_EVIDENCE", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
