#!/usr/bin/env python3
"""Offline, read-only SHA-256 verification of a source-only staging ZIP.

The stage contains historical scripts, some unsafe to run. This program only
reads bytes and prints JSON. Never imports or executes archived source code.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile

INDEX = "provenance/source_recovery_code_index_20261020.csv"
STATUS = "provenance/source_recovery_package_status_20261020.json"


class RecoveryIntegrityError(ValueError):
    """A recovered source ZIP failed an integrity or safety assertion."""


def verify(archive: Path) -> dict:
    with ZipFile(archive, "r") as handle:
        infos = handle.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise RecoveryIntegrityError("Duplicate ZIP member names")
        for name in names:
            path = PurePosixPath(name)
            if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
                raise RecoveryIntegrityError(f"Invalid member path: {name}")
            if path.as_posix() != name or name.endswith("/"):
                raise RecoveryIntegrityError(f"Non-canonical or directory member: {name}")
            if ((handle.getinfo(name).external_attr >> 16) & 0o170000) == 0o120000:
                raise RecoveryIntegrityError(f"Symlink member refused: {name}")
        if INDEX not in names or STATUS not in names:
            raise RecoveryIntegrityError("Missing required metadata")
        rows = list(csv.DictReader(io.StringIO(handle.read(INDEX).decode("utf-8-sig"))))
        status = json.loads(handle.read(STATUS))
        if not rows or len(rows) != int(status["total_source_files"]):
            raise RecoveryIntegrityError("Manifest count mismatch")
        required = {"repo_destination", "sha256", "bytes", "source_set", "source_archive_sha256"}
        if not required.issubset(rows[0]):
            raise RecoveryIntegrityError("Missing required manifest columns")
        paths = [row["repo_destination"] for row in rows]
        if len(set(paths)) != len(paths):
            raise RecoveryIntegrityError("Duplicate indexed destinations")
        expected_metadata = {
            INDEX,
            STATUS,
            "provenance/source_recovery_archive_summary_20261020.csv",
            "provenance/source_recovery_exclusions_20261020.csv",
        }
        if set(paths) != set(names) - expected_metadata:
            raise RecoveryIntegrityError("Unindexed source file or missing indexed member")
        for row in rows:
            name = row["repo_destination"]
            if not name.startswith("historical/"):
                raise RecoveryIntegrityError(f"Unexpected promoted active path: {name}")
            data = handle.read(name)
            if len(data) != int(row["bytes"]):
                raise RecoveryIntegrityError(f"Size mismatch: {name}")
            if hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise RecoveryIntegrityError(f"SHA mismatch: {name}")
        return {
            "status": "PASS",
            "source_files": len(rows),
            "groups": dict(Counter(row["source_set"] for row in rows)),
            "package_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "archive_members": len(names),
            "source_status": "HISTORICAL_UNREVIEWED_NOT_EXECUTED",
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_staging_zip", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.source_staging_zip)
    except (OSError, KeyError, ValueError, TypeError, UnicodeError, BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        raise SystemExit(1)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
