"""Fail-closed, read-only reconciliation of frozen C1-positive -> C5 -> C6 -> D1.

No network, scanner calls, SQLite access, source mutations or output of private
case-level identifiers.  Inputs are separately approved frozen local CSV copies;
GitHub CI runs synthetic fixtures only.

This establishes stored-record membership consistency, NOT whether any scanner
finding was valid, the original decision boundary was correctly annotated,
or empirical/statistical results were independently reproduced.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[1]

# Digests independently computed by complete read-only byte retrieval on
# 22 October 2026, checking per-chunk SHA-256 first. The C1 roster digest
# additionally matches the archived C1/SHA256SUMS.txt record.
FROZEN = {
    "c1_positive": {"bytes": 40984, "sha256": "adfdd519c81e77ecef095f11ee18692510774e714fdbc48fe98cb7345b08bddc"},
    "c5_pc_to_root": {"bytes": 194148, "sha256": "f28dcb3f7ed31b2dacb67ef0a449b7c25c700d7c12ff11f53a14080397302382"},
    "c6_root_census": {"bytes": 179190, "sha256": "97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c"},
    "d1_root_index": {"bytes": 66543, "sha256": "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3"},
}
EXPECTED = {
    "positive_cases": 192,
    "mapped_cases": 191,
    "producing_changes": 455,
    "roots": 342,
    "unmapped_positive_case_ids": ["17701"],
    "root_size_distribution": {"1": 283, "2": 36, "3": 9, "4": 7, "5": 3, "6": 3, "12": 1},
}
COLUMNS = {
    "c1_positive": {"positive_case_id", "repository"},
    "c5_pc_to_root": {"PC ID", "Case ID", "Repository", "Root ID", "Root PC Count"},
    "c6_root_census": {"Root ID", "Case ID", "Repository", "PC Count", "Producing Change IDs"},
    "d1_root_index": {"Root ID", "Case ID", "Repository", "PC Count", "PC IDs"},
}
MAX_SIZE = 8 * 1024 * 1024


class RootLineageError(ValueError):
    """Frozen source bytes, membership or schema fail a required invariant."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RootLineageError(message)


def canonical_case(value: str) -> str:
    require(isinstance(value, str) and value.isascii() and value.isdecimal()
            and str(int(value)) == value, "Invalid/noncanonical case identifier")
    return value


def count(value: str, label: str) -> int:
    require(isinstance(value, str) and value.isascii() and value.isdecimal(),
            f"{label} must be a nonnegative integer")
    return int(value)


def members(text: str, separator: str, label: str) -> list[str]:
    require(isinstance(text, str) and bool(text), f"Missing {label}")
    tokens = [value.strip() for value in text.split(separator)]
    require(all(tokens) and len(tokens) == len(set(tokens)),
            f"Missing or duplicate {label}")
    return tokens


def _stat(path: Path) -> tuple[int, int, int, int, int]:
    st = path.stat()
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _read_verified(path: Path, label: str, fingerprint: dict) -> list[dict[str, str]]:
    path = path.absolute()
    require(path != ROOT and ROOT not in path.parents,
            "Private frozen inputs cannot be inside the Git checkout")
    require(all(not p.is_symlink() for p in (path, *path.parents)),
            "Symlink in private frozen input path")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
            "Private frozen input is missing or nonregular")
    initial = _stat(path)
    require(initial[2] == fingerprint["bytes"] and 0 < initial[2] <= MAX_SIZE,
            "Frozen CSV size does not match recorded bytes")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == fingerprint["sha256"],
            "Frozen CSV SHA-256 does not match source-verified bytes")
    require(_stat(path) == initial, "Frozen CSV changed while being read")
    require(b"\x00" not in raw, "NUL byte in frozen CSV")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as exc:
        raise RootLineageError("Invalid frozen CSV text encoding") from exc
    with io.StringIO(text, newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        header = reader.fieldnames
        require(header is not None and len(header) == len(set(header))
                and COLUMNS[label] <= set(header),
                "Frozen CSV missing/duplicating required columns")
        rows = list(reader)
    require(bool(rows) and all(None not in row and all(
        isinstance(v, str) for v in row.values()) for row in rows),
        "Malformed frozen CSV row")
    require(_stat(path) == initial, "Frozen CSV changed while being parsed")
    return rows


def verify_root_lineage(c1_positive: Path, c5_pc_to_root: Path,
                        c6_root_census: Path, d1_root_index: Path, *,
                        fingerprints: dict | None = None,
                        expected: dict | None = None) -> dict:
    """Verify all frozen crosswalks. Overrides exist ONLY for synthetic tests.

    The public CLI never accepts modified fingerprints or expected counts.
    Returns aggregate-only evidence and keeps all case-level rows private.
    """
    fingerprints = FROZEN if fingerprints is None else fingerprints
    expected = EXPECTED if expected is None else expected
    files = {"c1_positive": c1_positive, "c5_pc_to_root": c5_pc_to_root,
             "c6_root_census": c6_root_census, "d1_root_index": d1_root_index}
    rows = {name: _read_verified(path, name, fingerprints[name])
            for name, path in files.items()}

    positives: dict[str, str] = {}
    for row in rows["c1_positive"]:
        case = canonical_case(row["positive_case_id"])
        require(case not in positives, "Repeated case in frozen positive roster")
        repo = row["repository"]
        require(bool(repo.strip()) and repo == repo.strip(),
                "Missing/malformed positive repository")
        positives[case] = repo

    pc_ids: set[str] = set()
    roots: dict[str, dict] = {}
    for row in rows["c5_pc_to_root"]:
        pc = row["PC ID"].strip()
        root = row["Root ID"].strip()
        case = canonical_case(row["Case ID"])
        repo = row["Repository"]
        require(bool(pc) and bool(root) and pc not in pc_ids,
                "Blank or repeated producing-change ID")
        require(case in positives and repo == positives[case],
                "Producing change case/repository outside frozen positive roster")
        pc_ids.add(pc)
        if root not in roots:
            roots[root] = {"case": case, "repository": repo,
                           "pcs": [], "reported_counts": set()}
        entry = roots[root]
        require(case == entry["case"] and repo == entry["repository"],
                "Root spans multiple cases or repositories")
        entry["pcs"].append(pc)
        entry["reported_counts"].add(count(row["Root PC Count"], "C5 root size"))
    for entry in roots.values():
        require(entry["reported_counts"] == {len(entry["pcs"])},
                "C5 within-root producing-change size inconsistent")

    def verify_index(name: str, id_column: str, delimiter: str) -> None:
        seen_roots: set[str] = set()
        seen_pcs: set[str] = set()
        for row in rows[name]:
            root = row["Root ID"].strip()
            require(root in roots and root not in seen_roots,
                    "Duplicate/unknown root in independent crosswalk")
            seen_roots.add(root)
            entry = roots[root]
            require(canonical_case(row["Case ID"]) == entry["case"]
                    and row["Repository"] == entry["repository"],
                    "Root index case/repository disagrees with C5")
            tokens = members(row[id_column], delimiter, "root PC membership")
            require(len(tokens) == count(row["PC Count"], "root count")
                    == len(entry["pcs"]) and set(tokens) == set(entry["pcs"]),
                    "Root index membership/size disagrees with C5")
            require(not (set(tokens) & seen_pcs),
                    "Producing change reused across root-index entries")
            seen_pcs.update(tokens)
        require(seen_roots == set(roots) and seen_pcs == pc_ids,
                "Independent root index has missing/extra root or PC")

    verify_index("c6_root_census", "Producing Change IDs", ";")
    verify_index("d1_root_index", "PC IDs", "|")
    mapped_cases = {entry["case"] for entry in roots.values()}
    unmapped = sorted(set(positives) - mapped_cases, key=int)
    histogram: dict[str, int] = {}
    for entry in roots.values():
        size = str(len(entry["pcs"]))
        histogram[size] = histogram.get(size, 0) + 1
    require(len(positives) == expected["positive_cases"] and
            len(mapped_cases) == expected["mapped_cases"] and
            len(pc_ids) == expected["producing_changes"] and
            len(roots) == expected["roots"] and
            unmapped == expected["unmapped_positive_case_ids"] and
            histogram == expected["root_size_distribution"],
            "Root-lineage counts, root sizes or unmapped set differ from freeze")
    return {
        "status": "PASS_BYTE_VERIFIED_FROZEN_POSITIVE_TO_ROOT_CROSSWALK_ONLY",
        "positive_roster_cases": len(positives),
        "positive_cases_with_roots": len(mapped_cases),
        "positive_cases_without_roots": len(unmapped),
        "unmapped_positive_case_ids": unmapped,
        "unique_producing_changes": len(pc_ids),
        "unique_roots": len(roots),
        "root_size_distribution": dict(sorted(histogram.items(), key=lambda p: int(p[0]))),
        "byte_sha256_verified_for_all_four_inputs": True,
        "crossfile_membership_discrepancies": 0,
        "original_final_sqlite_authenticated": False,
        "original_scanner_outcomes_recomputed": False,
        "security_validity_human_adjudicated": False,
        "root_decision_annotations_independently_redone": False,
        "statistical_results_reproduced": False,
        "note": "Verifies four exact frozen source files and their stored lineage, "
                "not original scanner correctness or scientific replication.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("c1_positive_csv", type=Path)
    parser.add_argument("c5_pc_to_root_csv", type=Path)
    parser.add_argument("c6_root_census_csv", type=Path)
    parser.add_argument("d1_root_index_csv", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_root_lineage(args.c1_positive_csv, args.c5_pc_to_root_csv,
                                     args.c6_root_census_csv, args.d1_root_index_csv)
        status = 0
    except (RootLineageError, OSError, ValueError, TypeError, KeyError,
            UnicodeError, csv.Error) as exc:
        result = {"status": "BLOCKED_FROZEN_ROOT_LINEAGE_INPUT",
                  "error": str(exc), "scientific_replication_complete": False}
        status = 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return status


if __name__ == "__main__":
    sys.exit(main())
