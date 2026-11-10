"""Offline, byte-locked reconciliation of C1 positives and C5/C6/D1 roots.

Original CSV files must be supplied separately, outside the Git checkout.
Only CSV contents are read; no DB, scanner, Wits, GitHub, or artifact mutation.
The check establishes frozen *membership*, never scanner/causal correctness.
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

# Read-only original Wits artifact bytes independently SHA-verified on 2026-10-22.
SOURCE_SPECS = {
    "c1_positive": (
        40984, "adfdd519c81e77ecef095f11ee18692510774e714fdbc48fe98cb7345b08bddc",
    ),
    "c5_pc_root": (
        194148, "f28dcb3f7ed31b2dacb67ef0a449b7c25c700d7c12ff11f53a14080397302382",
    ),
    "c6_roots": (
        179190, "97e989ef8b3f86413fc821d97c78a15701bdd8e2cb4fdb020ffdc64c4554762c",
    ),
    "d1_root_index": (
        66543, "ff1432d1959b501f62a9aeb18dface0976db11dbc59d31a233a24a816236ddf3",
    ),
}
EXPECTED_COUNTS = {
    "positives": 192,
    "mapped_cases": 191,
    "pcs": 455,
    "roots": 342,
    "unmapped": {"17701"},
    "root_sizes": {1: 283, 2: 36, 3: 9, 4: 7, 5: 3, 6: 3, 12: 1},
}
REQUIRED_COLUMNS = {
    "c1_positive": {"positive_case_id", "repository"},
    "c5_pc_root": {
        "PC ID", "Case ID", "Repository", "Root ID", "Root PC Count",
    },
    "c6_roots": {
        "Root ID", "Case ID", "Repository", "PC Count", "Producing Change IDs",
    },
    "d1_root_index": {
        "Root ID", "Case ID", "Repository", "PC Count", "PC IDs",
    },
}


class CrosswalkError(ValueError):
    """A source identity, CSV invariant, or frozen cohort link was violated."""


def _require(value: bool, explanation: str) -> None:
    if not value:
        raise CrosswalkError(explanation)


def _checked_local_file(path: Path, label: str, size: int) -> tuple[Path, tuple]:
    _require(".." not in path.parts, f"{label}: path traversal is not allowed")
    path = path.absolute()
    _require(path != ROOT and ROOT not in path.parents,
             f"{label}: original CSVs cannot be staged inside Git checkout")
    for component in (path, *path.parents):
        _require(not component.is_symlink(), f"{label}: path contains symlink")
    _require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
             f"{label}: expected an existing regular file")
    s = path.stat()
    identity = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    _require(s.st_size == size and 0 < size <= 16 * 1024 * 1024,
             f"{label}: frozen byte length disagrees")
    return path, identity


def _read_source(path: Path, label: str, spec: tuple[int, str]) -> list[dict[str, str]]:
    size, expected_hash = spec
    path, before = _checked_local_file(path, label, size)
    body = path.read_bytes()
    _require(hashlib.sha256(body).hexdigest() == expected_hash,
             f"{label}: frozen SHA-256 differs")
    try:
        text = body.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        head = reader.fieldnames
        _require(head is not None and len(set(head)) == len(head) and
                 REQUIRED_COLUMNS[label] <= set(head),
                 f"{label}: missing/duplicate CSV columns")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise CrosswalkError(f"{label}: malformed CSV encoding/content") from exc
    _require(bool(rows) and all(
        None not in row and all(value is not None for value in row.values())
        for row in rows
    ), f"{label}: empty or malformed CSV records")
    s = path.stat()
    after = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    _require(before == after, f"{label}: original CSV changed while checking")
    return rows


def _items(value: str, delimiter: str, role: str) -> list[str]:
    tokens = [v.strip() for v in value.split(delimiter)]
    _require(bool(tokens) and all(tokens) and len(tokens) == len(set(tokens)),
             f"{role}: empty/duplicate producing change IDs")
    return tokens


def _positive_number(value: str, role: str) -> int:
    _require(value.isascii() and value.isdecimal() and
             (not value.startswith("0") or value == "0"),
             f"{role}: noncanonical decimal count")
    number = int(value)
    _require(number > 0, f"{role}: positive integer required")
    return number


def verify_frozen_root_chain(
    paths: dict[str, Path], *,
    specs: dict[str, tuple[int, str]] | None = None,
    expected: dict | None = None,
) -> dict:
    """Verify four frozen row sources; overrides are synthetic-test-only.

    The public CLI always uses the hardcoded SOURCE_SPECS and EXPECTED_COUNTS.
    """
    specs = SOURCE_SPECS if specs is None else specs
    expected = EXPECTED_COUNTS if expected is None else expected
    _require(set(paths) == set(SOURCE_SPECS) == set(specs),
             "Four explicitly named source files are required")
    rows = {name: _read_source(paths[name], name, specs[name]) for name in SOURCE_SPECS}

    positives = {}
    for item in rows["c1_positive"]:
        case_id = item["positive_case_id"]
        _require(case_id.isascii() and case_id.isdecimal() and
                 case_id not in positives and bool(item["repository"].strip()),
                 "C1 positive roster has duplicate/malformed case or repository")
        positives[case_id] = item["repository"]

    groups = {}
    pcs = set()
    for item in rows["c5_pc_root"]:
        pc, root, case_id = item["PC ID"], item["Root ID"], item["Case ID"]
        repository = item["Repository"]
        _require(pc and root and case_id.isascii() and case_id.isdecimal()
                 and bool(repository.strip()) and pc not in pcs,
                 "C5 has duplicate/missing PC, root, case or repository")
        pcs.add(pc)
        group = groups.setdefault(root, {
            "case_id": case_id, "repository": repository,
            "pc_ids": set(), "declared_count": set(),
        })
        _require(group["case_id"] == case_id and
                 group["repository"] == repository,
                 "C5 root crosses workflow/repository boundaries")
        group["pc_ids"].add(pc)
        group["declared_count"].add(
            _positive_number(item["Root PC Count"], "C5 root PC count")
        )

    def compare_root_source(label: str, id_column: str, separator: str) -> None:
        seen, all_members = set(), set()
        for item in rows[label]:
            root = item["Root ID"]
            _require(root in groups and root not in seen,
                     f"{label}: unknown/duplicate root")
            seen.add(root)
            group = groups[root]
            members = _items(item[id_column], separator, label)
            _require(set(members) == group["pc_ids"] and
                     item["Case ID"] == group["case_id"] and
                     item["Repository"] == group["repository"] and
                     _positive_number(item["PC Count"], label) == len(members),
                     f"{label}: PC, case, repository or count disagrees with C5")
            _require(all(v not in all_members for v in members),
                     f"{label}: producing change assigned to multiple roots")
            all_members.update(members)
        _require(seen == set(groups) and all_members == pcs,
                 f"{label}: missing roots or producing changes")

    compare_root_source("c6_roots", "Producing Change IDs", ";")
    compare_root_source("d1_root_index", "PC IDs", "|")

    mapped_cases = {}
    distribution = {}
    for root, group in groups.items():
        case_id = group["case_id"]
        _require(case_id in positives and positives[case_id] == group["repository"],
                 "A mapped root workflow is not a C1 positive or repository differs")
        mapped_cases[case_id] = group["repository"]
        count = len(group["pc_ids"])
        _require(group["declared_count"] == {count},
                 "C5 root-count annotations disagree with actual membership")
        distribution[count] = distribution.get(count, 0) + 1

    omitted = set(positives) - set(mapped_cases)
    _require(len(rows["c1_positive"]) == len(positives) == expected["positives"] and
             len(mapped_cases) == expected["mapped_cases"] and
             len(pcs) == expected["pcs"] and
             len(groups) == expected["roots"] and
             omitted == set(expected["unmapped"]) and
             distribution == expected["root_sizes"],
             "Frozen C1 positive → C5/C6/D1 root population mismatch")
    return {
        "status": "PASS_FROZEN_C1_TO_C5_C6_D1_MEMBERSHIP_ONLY",
        "sha256_and_bytes_verified": True,
        "c1_positive_cases": len(positives),
        "root_mapped_positive_workflows": len(mapped_cases),
        "distinct_producing_changes": len(pcs),
        "distinct_root_decisions": len(groups),
        "unmapped_positive_count": len(omitted),
        "unmapped_positive_ids": sorted(omitted),
        "root_size_distribution": {str(k): v for k, v in sorted(distribution.items())},
        "cross_file_membership_discrepancies": 0,
        "final_aug29_sqlite_verified": False,
        "scanner_results_reproduced": False,
        "root_coding_validity_human_adjudicated": False,
        "statistical_results_reproduced": False,
        "causal_claims_supported": False,
        "note": "Checks frozen recorded row-level membership, not underlying empirical truth.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in SOURCE_SPECS:
        parser.add_argument(name, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_frozen_root_chain({
            name: getattr(args, name) for name in SOURCE_SPECS
        })
        status = 0
    except (CrosswalkError, OSError, ValueError, TypeError, KeyError, csv.Error) as exc:
        result = {
            "status": "BLOCKED_FROZEN_ROOT_CHAIN_INPUT_OR_MEMBERSHIP",
            "error": str(exc),
            "scientific_reproduction": False,
        }
        status = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    sys.exit(main())
