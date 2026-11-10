"""Read-only verification of Git-imported frozen research source bytes.

Checks exactly 1,075 indexed preserved source files and two separately
attested CodeQL evaluators against their *committed* SHA-256 inventories.
Never imports/executes archived files, contacts the network or changes data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
PREFIX = {
    "MINER_AUG17": "historical/miner/2026-08-17/",
    "MINER_AUG19": "historical/miner/2026-08-19/",
    "MINER_LIVE": "historical/miner/2026-10-20-live-export/",
    "DISCOVERY_V21": "historical/discovery/v2_1_cluster/",
    "DISCOVERY_V22": "historical/discovery/v2_2_cluster/",
    "DECISION_STEP7": "historical/decision_controls/step7_collector/",
    "OCTOBER_JOBS": "historical/experiments/october_jobs/",
}
DOCUMENTATION_ONLY = {"historical/README.md"}


class ImportedSourceError(ValueError):
    """Source archive bytes or manifest metadata do not match."""


def _require(ok: bool, message: str):
    if not ok:
        raise ImportedSourceError(message)


def _csv(path: Path, fields: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        data = csv.DictReader(handle)
        _require(data.fieldnames is not None and
                 fields.issubset(data.fieldnames), f"Missing metadata columns {path}")
        rows = list(data)
    _require(bool(rows) and not any(None in r for r in rows),
             f"Malformed metadata rows {path}")
    return rows


def safe_relative_path(value: str) -> str:
    pure = PurePosixPath(value)
    _require(value and value.startswith("historical/"), "Outside historical root")
    _require("\\" not in value and not pure.is_absolute(), "Invalid path syntax")
    _require(value == pure.as_posix() and
             not any(p in ("", ".", "..") for p in value.split("/")),
             "Noncanonical/traversal historical file")
    return value


def _verify_file(root: Path, relative: str, digest: str, length: int) -> None:
    path = root / safe_relative_path(relative)
    _require(bool(HEX64.fullmatch(digest)), f"Invalid source SHA-256: {relative}")
    _require(length >= 0, f"Invalid byte length: {relative}")
    parent = path
    while parent != root:
        _require(not parent.is_symlink(), f"Symlink refused: {relative}")
        parent = parent.parent
    _require(path.is_file(), f"Missing frozen historical file: {relative}")
    _require(path.stat().st_size == length, f"Wrong historical byte size: {relative}")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    _require(h.hexdigest() == digest, f"Changed frozen historical source: {relative}")


def verify_imported_sources(repo_root: Path = ROOT) -> dict:
    repo_root = repo_root.absolute()
    _require(not repo_root.is_symlink() and repo_root.is_dir(),
             "Repository root must be a real directory")
    _require((repo_root / "historical").is_dir() and
             not (repo_root / "historical").is_symlink(),
             "Missing/nonregular historical directory")
    provenance = repo_root / "provenance"
    rows = _csv(provenance / "source_recovery_code_index_20261020.csv", {
        "source_set", "source_archive", "source_archive_sha256",
        "source_relative_path", "repo_destination", "sha256", "bytes",
    })
    statuses = json.loads(
        (provenance / "source_recovery_package_status_20261020.json").read_text(
            encoding="utf-8"
        )
    )
    origin = _csv(provenance / "source_recovery_archive_summary_20261020.csv", {
        "source_set", "archive", "archive_sha256", "staged_files", "staged_bytes",
    })
    origin_index = {r["source_set"]: r for r in origin}
    _require(set(origin_index) == set(PREFIX) and len(origin) == len(PREFIX),
             "Source-group summary missing/duplicate")
    _require(len(rows) == 1075 ==
             statuses.get("total_source_files"),
             "Historical source count does not equal 1,075")
    _require(statuses.get("source_files_bytes") == 11926471,
             "Original source byte total changed")
    _require(statuses.get("source_groups") ==
             {k: int(origin_index[k]["staged_files"]) for k in PREFIX},
             "Archive source counts do not agree")
    _require(statuses.get("no_cluster_operations") is True,
             "Archive policy unexpectedly changed")
    indexed = set()
    count = Counter()
    lengths = Counter()
    for row in rows:
        group = row["source_set"]
        _require(group in PREFIX, f"Unknown source group {group}")
        relative = row["source_relative_path"]
        full = safe_relative_path(row["repo_destination"])
        _require(full == PREFIX[group] + relative,
                 f"Archive-relative source path diverged {full}")
        _require(full not in indexed, f"Duplicate indexed source path: {full}")
        indexed.add(full)
        archive = origin_index[group]
        _require(
            row["source_archive"] == archive["archive"] and
            row["source_archive_sha256"] == archive["archive_sha256"],
            f"Source origin hash/name changed: {group}"
        )
        try:
            size = int(row["bytes"])
        except (TypeError, ValueError) as exc:
            raise ImportedSourceError(f"Bad manifest byte count {full}") from exc
        _verify_file(repo_root, full, row["sha256"], size)
        count[group] += 1
        lengths[group] += size
    _require(dict(count) == statuses["source_groups"],
             "Imported source counts do not match frozen manifest")
    _require(sum(lengths.values()) == statuses["source_files_bytes"],
             "Indexed source byte counts do not match frozen manifest")
    for group in PREFIX:
        _require(
            lengths[group] == int(origin_index[group]["staged_bytes"]),
            f"Per-group original byte count differs: {group}"
        )

    evaluators = json.loads(
        (provenance / "phase2_evaluator_sources.json").read_text(encoding="utf-8")
    )
    _require(evaluators.get("status") == "HISTORICAL_UNSAFE_TO_EXECUTE",
             "Phase2 scripts unexpectedly promoted to runnable")
    separately_attested = set()
    extra_bytes = 0
    _require(len(evaluators.get("files", [])) == 2,
             "Expected exactly two separately recovered CodeQL evaluators")
    for row in evaluators["files"]:
        name = safe_relative_path(row["path"])
        _require(name.startswith("historical/codeql_phase2/"),
                 "Evaluator outside CodeQL archival path")
        _require(name not in separately_attested and name not in indexed,
                 "Duplicate CodeQL evaluator entry")
        _require(row.get("mutates_file_system") is True,
                 "Unsafe evaluator side effects not recorded")
        _verify_file(repo_root, name, row["sha256"], int(row["bytes"]))
        separately_attested.add(name)
        extra_bytes += int(row["bytes"])

    actual = set()
    for path in (repo_root / "historical").rglob("*"):
        _require(not path.is_symlink(), "Symlink within historical tree")
        if path.is_file():
            actual.add(path.relative_to(repo_root).as_posix())
    allowed = indexed | separately_attested | DOCUMENTATION_ONLY
    _require(actual == allowed,
             "Unexpected or missing historical paths: " +
             repr(sorted((actual - allowed) | (allowed - actual))[:10]))
    return {
        "status": "PASS_ARCHIVED_SOURCE_BYTES_ONLY",
        "indexed_source_files_verified": len(indexed),
        "indexed_source_bytes_verified": sum(lengths.values()),
        "original_source_groups_verified": dict(sorted(count.items())),
        "additional_codeql_evaluators_verified": len(separately_attested),
        "additional_evaluator_bytes_verified": extra_bytes,
        "documentation_only_unindexed_paths": sorted(DOCUMENTATION_ONLY),
        "historical_files_executed": False,
        "historical_results_recomputed": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        result = verify_imported_sources(args.repository)
    except (ImportedSourceError, ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "FAIL_SOURCE_INTEGRITY", "error": str(exc)},
                         indent=2))
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
