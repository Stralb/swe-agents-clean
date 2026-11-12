#!/usr/bin/env python3
"""Compare canonical miner source trees in an August ZIP and live TAR.

Only source/config-like paths under selected code directories are considered;
historical backups and runtime data are explicitly omitted from this *active*
comparison. The original archives stay unchanged.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

SOURCE_DIRS = ("src/", "scripts/", "tests/", "ui/", "analysis/")
SNAPSHOT_ROOTS = ("malicious-issue-miner-rate-smart-main/", "malicious-issue-miner-rate-smart/")


def canonical_path(path: str) -> str | None:
    for root in SNAPSHOT_ROOTS:
        if path.startswith(root):
            path = path[len(root):]
            break
    else:
        return None
    if not path.startswith(SOURCE_DIRS):
        return None
    # These are not canonical source modules, even when they reside under src/.
    if any(name.startswith(".") for name in path.split("/")):
        return None
    if path.endswith((".bak", ".pyc")) or ".before_" in path or ".before-" in path:
        return None
    return path


def snapshot_hashes(archive: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as handle:
            for item in handle.infolist():
                path = canonical_path(item.filename)
                if path is None or item.is_dir():
                    continue
                if path in result:
                    raise ValueError(f"Duplicate source path: {path}")
                with handle.open(item) as source:
                    result[path] = hashlib.sha256(source.read()).hexdigest()
    else:
        with tarfile.open(archive, "r:gz") as handle:
            for item in handle:
                path = canonical_path(item.name)
                if path is None or not item.isfile():
                    continue
                if path in result:
                    raise ValueError(f"Duplicate source path: {path}")
                stream = handle.extractfile(item)
                if stream is None:
                    raise ValueError(f"Unreadable member: {path}")
                result[path] = hashlib.sha256(stream.read()).hexdigest()
    return result


def compare(aug17: Path, aug19: Path, live: Path) -> tuple[dict, list[dict]]:
    sets = {"aug17": snapshot_hashes(aug17), "aug19": snapshot_hashes(aug19), "live": snapshot_hashes(live)}
    rows = []
    for path in sorted(set().union(*map(set, sets.values()))):
        hashes = {k: v.get(path, "") for k, v in sets.items()}
        present = [k for k in sets if hashes[k]]
        if len(present) == 3 and len(set(hashes.values())) == 1:
            state = "IDENTICAL_ALL_THREE"
        elif len(present) == 1:
            state = "ONLY_" + present[0].upper()
        elif "live" not in present:
            state = "HISTORICAL_ONLY"
        elif "aug17" not in present:
            state = "ADDED_AFTER_AUG17"
        elif hashes["live"] != hashes["aug17"]:
            state = "LIVE_DIFFERS_FROM_AUG17"
        elif "aug19" in present and hashes["aug19"] != hashes["live"]:
            state = "AUG19_ONLY_VARIANT"
        else:
            state = "UNCHANGED_SINCE_AUG17"
        rows.append({"source_path": path, "aug17_sha256": hashes["aug17"],
                     "aug19_sha256": hashes["aug19"], "live_sha256": hashes["live"],
                     "classification": state})
    return {"path_count": len(rows), "snapshot_counts": {k: len(v) for k, v in sets.items()},
            "classifications": dict(Counter(r["classification"] for r in rows))}, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aug17", type=Path)
    parser.add_argument("aug19", type=Path)
    parser.add_argument("live", type=Path)
    parser.add_argument("--csv", type=Path, help="Optional local output path for per-file comparisons")
    args = parser.parse_args()
    summary, rows = compare(args.aug17, args.aug19, args.live)
    if args.csv:
        if args.csv.exists():
            parser.error("Refusing to overwrite an existing CSV")
        with args.csv.open("x", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
