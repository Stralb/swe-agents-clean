"""Read-only verification of the four frozen positive -> producing-change -> root tables.

No network, cluster access, SQLite migrations, scanners, or data writes.
Inputs are exact separately approved CSV copies outside the Git checkout.
This proves stored crosswalk consistency, not scanner correctness or replication.
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
MAX_BYTES = 8 * 1024 * 1024


class RootLineageError(ValueError):
    """Frozen bytes, source schema, or crosswalk membership violated."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RootLineageError(message)


def _stat(path: Path) -> tuple[int, int, int, int, int]:
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _case(value: str) -> str:
    require(isinstance(value, str) and value.isascii() and value.isdecimal()
            and str(int(value)) == value, "Noncanonical case identifier")
    return value


def _count(value: str) -> int:
    require(isinstance(value, str) and value.isascii() and value.isdecimal(),
            "Invalid nonnegative count")
    return int(value)


def _members(value: str, separator: str) -> list[str]:
    require(isinstance(value, str) and bool(value), "Missing PC membership")
    result = [x.strip() for x in value.split(separator)]
    require(all(result) and len(set(result)) == len(result),
            "Empty or duplicate PC membership")
    return result


def _csv(path: Path, role: str, fingerprint: dict) -> list[dict[str, str]]:
    path = path.absolute()
    require(path != ROOT and ROOT not in path.parents,
            "Frozen originals cannot be staged inside Git")
    require(all(not p.is_symlink() for p in (path, *path.parents)),
            "Symlink in private input path")
    require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
            "Frozen input is missing or nonregular")
    before = _stat(path)
    require(before[2] == fingerprint["bytes"] and 0 < before[2] <= MAX_BYTES,
            "Wrong frozen input byte size")
    payload = path.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == fingerprint["sha256"],
            "Frozen SHA-256 mismatch")
    require(_stat(path) == before, "Input changed during verification")
    require(b"\x00" not in payload, "NUL in CSV source")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeError as exc:
        raise RootLineageError("Invalid CSV encoding") from exc
    with io.StringIO(text, newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        header = reader.fieldnames
        require(header is not None and len(header) == len(set(header))
                and COLUMNS[role] <= set(header), "Invalid required CSV columns")
        rows = list(reader)
    require(bool(rows) and all(None not in row and
            all(isinstance(v, str) for v in row.values()) for row in rows),
            "Malformed CSV row")
    require(_stat(path) == before, "Input changed during parsing")
    return rows


def verify_root_lineage(c1_positive: Path, c5_pc_to_root: Path,
                        c6_root_census: Path, d1_root_index: Path, *,
                        fingerprints: dict | None = None,
                        expected: dict | None = None) -> dict:
    """Synthetic tests may override pins; the CLI never exposes overrides."""
    fingerprints = FROZEN if fingerprints is None else fingerprints
    expected = EXPECTED if expected is None else expected
    paths = dict(c1_positive=c1_positive, c5_pc_to_root=c5_pc_to_root,
                 c6_root_census=c6_root_census, d1_root_index=d1_root_index)
    tables = {name: _csv(path, name, fingerprints[name])
              for name, path in paths.items()}
    positives = {}
    for row in tables["c1_positive"]:
        case = _case(row["positive_case_id"])
        repo = row["repository"]
        require(case not in positives and repo == repo.strip() and bool(repo),
                "Invalid or duplicate positive roster record")
        positives[case] = repo

    pcs = set()
    roots = {}
    for row in tables["c5_pc_to_root"]:
        pc, root = row["PC ID"].strip(), row["Root ID"].strip()
        case, repo = _case(row["Case ID"]), row["Repository"]
        require(bool(pc) and bool(root) and pc not in pcs,
                "Blank or reused producing-change ID")
        require(case in positives and repo == positives[case],
                "Producing-change case/repository not in positive roster")
        pcs.add(pc)
        if root not in roots:
            roots[root] = {"case": case, "repo": repo, "members": set(),
                           "sizes": set()}
        entry = roots[root]
        require(entry["case"] == case and entry["repo"] == repo,
                "Root spans multiple cases or repositories")
        entry["members"].add(pc)
        entry["sizes"].add(_count(row["Root PC Count"]))
    for entry in roots.values():
        require(entry["sizes"] == {len(entry["members"])},
                "C5 root size disagreement")

    def compare(name: str, id_column: str, separator: str) -> None:
        visited_roots, visited_pcs = set(), set()
        for row in tables[name]:
            root = row["Root ID"].strip()
            require(root in roots and root not in visited_roots,
                    "Unknown or duplicate root in independent index")
            visited_roots.add(root)
            entry = roots[root]
            require(entry["case"] == _case(row["Case ID"]) and
                    entry["repo"] == row["Repository"],
                    "Crosswalk repository/case mismatch")
            members = _members(row[id_column], separator)
            require(len(members) == _count(row["PC Count"]) ==
                    len(entry["members"]) and set(members) == entry["members"],
                    "Crosswalk root membership/size mismatch")
            require(not visited_pcs.intersection(members),
                    "Duplicate PC across root-index entries")
            visited_pcs.update(members)
        require(visited_roots == set(roots) and visited_pcs == pcs,
                "Root index has missing/extra roots or PCs")

    compare("c6_root_census", "Producing Change IDs", ";")
    compare("d1_root_index", "PC IDs", "|")
    mapped = {entry["case"] for entry in roots.values()}
    unmapped = sorted(set(positives) - mapped, key=int)
    distribution = {}
    for entry in roots.values():
        k = str(len(entry["members"]))
        distribution[k] = distribution.get(k, 0) + 1
    require(len(positives) == expected["positive_cases"] and
            len(mapped) == expected["mapped_cases"] and
            len(pcs) == expected["producing_changes"] and
            len(roots) == expected["roots"] and
            unmapped == expected["unmapped_positive_case_ids"] and
            distribution == expected["root_size_distribution"],
            "Frozen lineage count, missing-positive, or root-size mismatch")
    return {
        "status": "PASS_BYTE_VERIFIED_FROZEN_POSITIVE_TO_ROOT_CROSSWALK_ONLY",
        "positive_roster_cases": len(positives),
        "positive_cases_with_roots": len(mapped),
        "positive_cases_without_roots": len(unmapped),
        "unmapped_positive_case_ids": unmapped,
        "unique_producing_changes": len(pcs),
        "unique_roots": len(roots),
        "root_size_distribution": dict(sorted(distribution.items(), key=lambda x: int(x[0]))),
        "crossfile_membership_discrepancies": 0,
        "all_four_source_sha256_verified": True,
        "original_final_sqlite_authenticated": False,
        "original_scanner_outcomes_recomputed": False,
        "statistical_results_reproduced": False,
        "causal_effects_reproduced": False,
        "note": "Stored lineage consistency only, not scanner validity or independent research replication.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("c1_positive", type=Path)
    parser.add_argument("c5_pc_to_root", type=Path)
    parser.add_argument("c6_root_census", type=Path)
    parser.add_argument("d1_root_index", type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify_root_lineage(args.c1_positive, args.c5_pc_to_root,
                                     args.c6_root_census, args.d1_root_index)
        code = 0
    except (RootLineageError, OSError, TypeError, ValueError, KeyError,
            UnicodeError, csv.Error) as exc:
        result = {"status": "BLOCKED_FROZEN_ROOT_LINEAGE_INPUT",
                  "error": str(exc), "scientific_replication_complete": False}
        code = 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
