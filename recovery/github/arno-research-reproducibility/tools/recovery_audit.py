#!/usr/bin/env python3
"""Read-only checks for the Arno research recovery artifacts.

No archive extraction, network access, database writes or cluster operations.
The archive comparison tools operate on local copies and fail closed when
expected members, columns, unique identifiers or accounting invariants differ.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import tarfile
from collections import Counter
from pathlib import Path


class AuditError(ValueError):
    """An artifact failed a required reproducibility assertion."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(manifest: Path, search_dir: Path) -> dict:
    """Verify all manifest rows by basename; missing files are not silently skipped."""
    with manifest.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"artifact_id", "filename", "sha256", "bytes"}
    if not rows or not required.issubset(rows[0]):
        raise AuditError("Manifest is empty or required columns are absent")
    ids = [r["artifact_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise AuditError("Duplicate artifact_id in manifest")
    statuses = []
    for row in rows:
        name = row["filename"]
        if name != Path(name).name or name in ("", ".", ".."):
            raise AuditError(f"Invalid manifest filename: {name!r}")
        target = search_dir / name
        if not target.is_file() or target.is_symlink():
            statuses.append({"artifact_id": row["artifact_id"], "status": "MISSING"})
            continue
        try:
            expected_size = int(row["bytes"])
        except ValueError as exc:
            raise AuditError(f"Invalid expected byte count for {name}") from exc
        actual_size = target.stat().st_size
        actual_hash = sha256_file(target) if actual_size == expected_size else None
        status = "PASS" if actual_hash == row["sha256"].lower() else "MISMATCH"
        statuses.append({"artifact_id": row["artifact_id"], "status": status})
    return {
        "manifest_rows": len(rows),
        "counts": dict(Counter(s["status"] for s in statuses)),
        "failures": [s for s in statuses if s["status"] != "PASS"],
    }


def read_csv_from_tar(archive: Path, suffix: str) -> list[dict[str, str]]:
    """Read one unambiguous regular CSV member without extracting any member."""
    with tarfile.open(archive, mode="r:gz") as handle:
        matches = [m for m in handle.getmembers() if m.isfile() and
                   (m.name == suffix or m.name.endswith("/" + suffix))]
        if len(matches) != 1:
            raise AuditError(f"Expected exactly one {suffix} in {archive.name}; found {len(matches)}")
        member = matches[0]
        if member.size > 64 * 1024 * 1024:
            raise AuditError(f"Refusing unusually large CSV member: {suffix}")
        stream = handle.extractfile(member)
        if stream is None:
            raise AuditError(f"Unreadable tar member: {suffix}")
        content = stream.read().decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(content)))
    if not rows:
        raise AuditError(f"No rows found: {suffix}")
    return rows


def require_unique(rows: list[dict], key: str, expected: int | None = None) -> dict:
    if any(key not in r or not r[key] for r in rows):
        raise AuditError(f"Missing or empty key: {key}")
    index = {r[key]: r for r in rows}
    if len(index) != len(rows):
        raise AuditError(f"Duplicate {key} rows")
    if expected is not None and len(rows) != expected:
        raise AuditError(f"Expected {expected} {key} rows; got {len(rows)}")
    return index


def audit_census(c_archive: Path) -> dict:
    roots = read_csv_from_tar(c_archive, "C6_ROOT_CENSUS.csv")
    pc_rows = read_csv_from_tar(c_archive, "C5_PC_TO_ROOT_FINAL.csv")
    roots_by_id = require_unique(roots, "Root ID", 342)
    require_unique(pc_rows, "PC ID", 455)
    observed = Counter(r["Root ID"] for r in pc_rows)
    if set(observed) != set(roots_by_id):
        raise AuditError("Root IDs in PC crosswalk do not match census")
    for root_id, root in roots_by_id.items():
        if observed[root_id] != int(root["PC Count"]):
            raise AuditError(f"Wrong PC membership count: {root_id}")
        related = [r for r in pc_rows if r["Root ID"] == root_id]
        if {r["Case ID"] for r in related} != {root["Case ID"]}:
            raise AuditError(f"Cross-workflow root found: {root_id}")
    workflows = len({r["Case ID"] for r in pc_rows})
    if workflows != 191:
        raise AuditError(f"Expected 191 workflows, found {workflows}")
    return {"status": "PASS", "roots": len(roots), "producing_changes": len(pc_rows),
            "workflows": workflows, "singleton_roots": sum(v == 1 for v in observed.values()),
            "multi_pc_roots": sum(v > 1 for v in observed.values())}


def compare_d_final_to_d7(d_archive: Path, d7_archive: Path) -> dict:
    d_rows = read_csv_from_tar(d_archive, "D5_FINAL_ROOT_CENSUS_342.csv")
    d7_rows = read_csv_from_tar(d7_archive, "D7_FINAL_ROOT_CENSUS_WITH_COHORTS_342.csv")
    d = require_unique(d_rows, "root_id", 342)
    d7 = require_unique(d7_rows, "root_id", 342)
    if set(d) != set(d7):
        raise AuditError("Root ID sets differ between frozen D exports")
    for root_id in d:
        if (d[root_id]["pc_ids"], d[root_id]["pc_count"]) != (
            d7[root_id]["pc_ids"], d7[root_id]["pc_count"]
        ):
            raise AuditError(f"Producing-change membership changed for {root_id}")
    changed = [
        {"root_id": key,
         "d_route": d[key]["final_route"], "d_tier": d[key]["final_tier"],
         "d7_route": d7[key]["final_route"], "d7_tier": d7[key]["final_tier"]}
        for key in sorted(d)
        if (d[key]["final_route"], d[key]["final_tier"]) !=
           (d7[key]["final_route"], d7[key]["final_tier"])
    ]
    return {"status": "UNRESOLVED_DIFFERENCE" if changed else "MATCH",
            "roots": len(d), "changed_rows": len(changed),
            "route_changes": sum(r["d_route"] != r["d7_route"] for r in changed),
            "tier_changes": sum(r["d_tier"] != r["d7_tier"] for r in changed),
            "d_route_counts": dict(Counter(r["final_route"] for r in d.values())),
            "d7_route_counts": dict(Counter(r["final_route"] for r in d7.values())),
            "differences": changed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify-manifest", help="Verify local copies against frozen SHA-256 manifest")
    verify.add_argument("manifest", type=Path)
    verify.add_argument("source_directory", type=Path)
    census = commands.add_parser("audit-census", help="Check frozen C root-to-producing-change crosswalk")
    census.add_argument("c_archive", type=Path)
    compare = commands.add_parser("compare-d", help="Compare frozen D and D7 route/tier labels")
    compare.add_argument("d_archive", type=Path)
    compare.add_argument("d7_archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-manifest":
            result = verify_manifest(args.manifest, args.source_directory)
            ok = not result["failures"]
        elif args.command == "audit-census":
            result = audit_census(args.c_archive)
            ok = True
        else:
            result = compare_d_final_to_d7(args.d_archive, args.d7_archive)
            # Known conflicts are informative; not a failure of archival integrity.
            ok = True
    except (AuditError, OSError, tarfile.TarError, UnicodeError) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
