"""Fail-closed, read-only intake of a separately approved frozen SQLite *copy*.

Never imports the original Database class, migrates SQLite, invokes GitHub,
runs a scanner, executes user SQL, or accesses the Wits cluster. SHA-256 proves
candidate byte identity only, not that the copy is the original research DB.

Use a private manifest containing a *previously established* SHA/byte length.
Never commit the real database or an identifying private manifest to Git.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CANDIDATE_ROLE = "historical_miner_sqlite_candidate"
IDENTITY = "UNVERIFIED_AS_ORIGINAL"
SNAPSHOT_METHODS = {
    "sqlite_backup_api",
    "sqlite_vacuum_into",
    "offline_checkpointed_copy",
}
REQUIRED_COLUMNS = {
    "repos": {"id", "full_name"},
    "issues": {"id", "repo_id", "number"},
    "pull_requests": {"id", "repo_id", "number", "base_sha", "head_sha"},
    "cases": {"id", "repo_id", "issue_id", "pr_id", "status"},
    "issue_pr_links": {"id", "issue_id", "pr_id"},
    "pr_files": {"id", "pr_id", "filename"},
    "scanner_runs": {"id", "case_id", "pr_id", "scanner", "status"},
    "scanner_findings": {
        "id", "case_id", "pr_id", "scanner", "finding_type", "introduced",
    },
}
COUNT_TABLES = (
    "repos", "issues", "pull_requests", "cases", "issue_pr_links",
    "pr_files", "scanner_runs", "scanner_findings", "excluded_cases",
    "scanner_jobs", "retrieval_queries",
)
SIDECARS = ("-wal", "-shm", "-journal")
DB_HEADER = b"SQLite format 3\x00"


class SnapshotIntakeError(ValueError):
    """A proposed candidate does not pass the read-only intake requirements."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise SnapshotIntakeError(message)


def _safe_regular_file(path: Path, *, role: str) -> Path:
    path = path.absolute()
    for segment in (path, *path.parents):
        _require(not segment.is_symlink(), f"{role} path contains a symlink")
    _require(path.is_file() and stat.S_ISREG(path.stat().st_mode),
             f"{role} is not an existing regular file")
    return path


def _manifest(path: Path) -> dict:
    path = _safe_regular_file(path, role="Private snapshot manifest")
    _require(path.stat().st_size < 65536, "Private manifest unexpectedly large")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise SnapshotIntakeError("Malformed private snapshot manifest") from exc
    _require(isinstance(data, dict), "Snapshot manifest must be an object")
    _require(type(data.get("schema_version")) is int and
             data["schema_version"] == 1, "Unknown snapshot manifest version")
    _require(data.get("artifact_role") == CANDIDATE_ROLE,
             "Unapproved snapshot manifest artifact role")
    _require(data.get("source_identity") == IDENTITY,
             "Manifest must not assert unproved original database identity")
    _require(data.get("capture_method") in SNAPSHOT_METHODS,
             "Missing/unapproved self-reported capture method")
    _require(isinstance(data.get("sha256"), str) and
             HEX64.fullmatch(data["sha256"]) is not None,
             "Expected one lowercase 64-digit SHA-256")
    _require(type(data.get("bytes")) is int and data["bytes"] >= 100,
             "Missing/invalid frozen copy byte length")
    return data


def _sidecars_absent(path: Path) -> None:
    for suffix in SIDECARS:
        target = Path(str(path) + suffix)
        _require(not target.exists() and not target.is_symlink(),
                 f"SQLite sidecar {suffix} exists: use a stable offline snapshot")


def _stable_stat(path: Path) -> tuple[int, int, int, int, int]:
    s = path.stat()
    return s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns


def _check_and_hash_copy(path: Path, manifest: dict) -> tuple[str, tuple]:
    path = _safe_regular_file(path, role="Staged SQLite candidate")
    _require(ROOT != path and ROOT not in path.parents,
             "Historical database bytes must not be staged in the Git repository")
    _sidecars_absent(path)
    initial = _stable_stat(path)
    _require(initial[2] == manifest["bytes"],
             "Snapshot byte length differs from private manifest")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        header = handle.read(100)
        _require(header.startswith(DB_HEADER),
                 "Staged candidate is not an SQLite main database file")
        _require((header[18], header[19]) in ((1, 1), (2, 2)),
                 "Unknown SQLite journal-header mode")
        digest.update(header)
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    _require(digest.hexdigest() == manifest["sha256"],
             "Snapshot SHA-256 differs from previously frozen manifest")
    _require(_stable_stat(path) == initial,
             "Snapshot changed while calculating SHA-256")
    _sidecars_absent(path)
    return ("wal_header" if header[18] == 2 else "rollback_header"), initial


def _intact_database(
    path: Path, *, integrity_deadline_seconds: float,
) -> dict:
    _require(0 < integrity_deadline_seconds <= 3600,
             "Integrity-check time budget must be within (0, 3600] seconds")
    # URI escaping comes from Path.as_uri(); immutable=1 means SQLite does not
    # acquire write locks or create -shm/-wal. Only a frozen *copy* is allowed.
    conn = sqlite3.connect(
        path.as_uri() + "?mode=ro&immutable=1",
        uri=True, timeout=2.0,
    )
    try:
        conn.enable_load_extension(False)
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA trusted_schema = OFF")
        conn.execute("PRAGMA foreign_keys = ON")
        _require(conn.execute("PRAGMA query_only").fetchone()[0] == 1,
                 "SQLite connection unexpectedly permits writes")
        aliases = conn.execute("PRAGMA database_list").fetchall()
        _require(len(aliases) == 1 and aliases[0][1] == "main",
                 "Unexpected attached database")
        _require(conn.execute("PRAGMA database_list").fetchone()[2] == str(path),
                 "Opened SQLite database path does not match approved candidate")
        limit = time.monotonic() + integrity_deadline_seconds
        conn.set_progress_handler(
            lambda: int(time.monotonic() > limit),
            10000,
        )
        try:
            status = conn.execute("PRAGMA integrity_check").fetchmany(2)
        finally:
            conn.set_progress_handler(None, 0)
        _require(status == [("ok",)],
                 "SQLite integrity_check did not return a single 'ok'")
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        missing_tables = set(REQUIRED_COLUMNS) - tables
        _require(not missing_tables,
                 "Missing required archived miner tables: " +
                 ", ".join(sorted(missing_tables)))
        for table, expected in REQUIRED_COLUMNS.items():
            # The identifier is always from hardcoded REQUIRED_COLUMNS, never
            # constructed from untrusted input or an arbitrary SQL file.
            columns = {
                record[1] for record in conn.execute(
                    f'PRAGMA table_info("{table}")'
                )
            }
            _require(expected <= columns,
                     f"Archived miner table missing required columns: {table}")
        schema = list(conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "ORDER BY type, name, tbl_name"
        ))
        schema_sha256 = hashlib.sha256(json.dumps(
            schema, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        counts = {}
        for table in COUNT_TABLES:
            if table in tables:
                # Fixed allowlist: never interpolate manifest/table names.
                counts[table] = conn.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]
        return {
            "sqlite_integrity_check": "ok",
            "minimal_archived_miner_schema": "compatible",
            "sqlite_schema_sha256": schema_sha256,
            "sqlite_user_version": conn.execute(
                "PRAGMA user_version"
            ).fetchone()[0],
            "sqlite_application_id": conn.execute(
                "PRAGMA application_id"
            ).fetchone()[0],
            "sqlite_page_count": conn.execute(
                "PRAGMA page_count"
            ).fetchone()[0],
            "known_table_counts_unfiltered": counts,
        }
    finally:
        conn.close()


def verify_candidate(
    database: Path, manifest_path: Path, *,
    integrity_deadline_seconds: float = 300.0,
) -> dict:
    """Validate immutable candidate only; no historical cohort conclusions."""
    manifest = _manifest(manifest_path)
    path = _safe_regular_file(database, role="Staged SQLite candidate")
    mode, initial_stat = _check_and_hash_copy(path, manifest)
    result = _intact_database(
        path, integrity_deadline_seconds=integrity_deadline_seconds,
    )
    _require(_stable_stat(path) == initial_stat,
             "Candidate SQLite file changed during inspection")
    _sidecars_absent(path)
    result.update({
        "status": "PASS_CANDIDATE_SQLITE_INTEGRITY_ONLY",
        "candidate_sha256": manifest["sha256"],
        "candidate_bytes": manifest["bytes"],
        "journal_header_mode": mode,
        "capture_method_self_reported": manifest["capture_method"],
        "original_source_identity_independently_verified": False,
        "historical_cohort_inclusion_sql_verified": False,
        "reported_3809_workflows_reproduced": False,
        "reported_192_positive_workflows_reproduced": False,
        "reported_455_producing_changes_reproduced": False,
        "statistical_results_reproduced": False,
        "warning": (
            "Unfiltered raw table counts are NOT cohort, scanner-positive, "
            "producing-change, control or causal analysis counts. "
            "An SHA-256 manifest created for a copy does not independently "
            "attest that it matches the original historical database."
        ),
    })
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "verify-candidate", help="Read-only identity and integrity check"
    )
    check.add_argument("database", type=Path)
    check.add_argument("private_manifest", type=Path)
    check.add_argument(
        "--integrity-seconds", type=float, default=300.0,
        help="Maximum time for SQLite integrity_check, default 300 seconds",
    )
    args = parser.parse_args(argv)
    try:
        report = verify_candidate(
            args.database, args.private_manifest,
            integrity_deadline_seconds=args.integrity_seconds,
        )
    except (SnapshotIntakeError, sqlite3.DatabaseError, OSError,
            ValueError, TypeError) as exc:
        print(json.dumps({
            "status": "BLOCKED_SQLITE_CANDIDATE_NOT_VERIFIED",
            "error": str(exc),
            "historical_counts_reproduced": False,
        }, indent=2))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
