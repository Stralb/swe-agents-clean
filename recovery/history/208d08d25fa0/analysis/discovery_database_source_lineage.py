"""Static archived provenance for the 3,809-case discovery SQLite snapshot.

AST-parse and SHA-verify source without importing/executing NumPy/Pandas/ML
or any archived script. A separately staged DB may be compared against this
exact source-declared SHA, then the original case-linkage SELECT replayed
read-only. None of this proves the 192/455 scanner-positive study denominators.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from analysis.frozen_sqlite_intake import (
    SnapshotIntakeError, verify_candidate,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = {
    "historical/miner/2026-10-20-live-export/analysis/full_corpus_discovery_v1_1/discovery.py":
        "d6b980ff758b548226c8a6b2099963fafdc02f093fe63fc2b09fc6a0b02e0ca2",
    "historical/miner/2026-10-20-live-export/analysis/full_corpus_deep_discovery_v2/deep_common.py":
        "ec9d4b7910403d9c1fc37e8954c4f1c929185dcc5a7cb26a3085166f73a88896",
    "historical/discovery/v2_2_cluster/v22_common.py":
        "9d0f6e93633543b60a46a4cd1adf40162af0415c44dd542a5377958b70774e27",
    "historical/discovery/v2_1_cluster/v21_common.py":
        "d9494f9b760d9024c9be9c46f8b3cb9247290aae9be8714dcbb7c00d15bca475",
    "historical/miner/2026-10-20-live-export/analysis/full_corpus_deep_discovery_v2/deep_extract.py":
        "699e8d597bb9940e261160904adb19f020bec0442f1dfe2e1b8805d8a1f307f7",
}
DECLARED_DISCOVERY_SHA256 = (
    "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa"
)
DECLARED_CASES = 3809
CASE_QUERY = (
    "SELECT id AS case_id, repo_id, issue_id, pr_id FROM cases ORDER BY id"
)


class DiscoveryLineageError(ValueError):
    """Source-embedded query, hash or replay invariant not established."""


def _source_ast(root: Path, relative: str) -> ast.Module:
    path = root / relative
    if path.is_symlink() or not path.is_file():
        raise DiscoveryLineageError(f"Missing/nonregular archived source: {relative}")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != SOURCE_SHA256[relative]:
        raise DiscoveryLineageError(f"Archived analysis source SHA mismatch: {relative}")
    return ast.parse(raw, filename=relative)


def _constant(tree: ast.Module, name: str):
    choices = []
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            choices.append(ast.literal_eval(node.value))
    if len(choices) != 1:
        raise DiscoveryLineageError(f"Expected one source constant {name}")
    return choices[0]


def archived_discovery_fingerprint(root: Path = ROOT) -> dict:
    root = root.absolute()
    scanned = {}
    for path in SOURCE_SHA256:
        scanned[path] = _source_ast(root, path)
    seen_shas = []
    for path, tree in scanned.items():
        count = _constant(tree, "EXPECTED_CASES") if not path.endswith(
            "/deep_extract.py"
        ) else None
        if count is not None and (type(count) is not int or count != DECLARED_CASES):
            raise DiscoveryLineageError(f"Unexpected case unit in {path}")
        if path.endswith("/v21_common.py") or path.endswith("/deep_extract.py"):
            continue
        value = _constant(tree, "EXPECTED_DB_SHA256")
        if value != DECLARED_DISCOVERY_SHA256:
            raise DiscoveryLineageError(f"Unexpected discovery DB SHA in {path}")
        seen_shas.append(value)
    if len(seen_shas) != 3:
        raise DiscoveryLineageError("Expected 3 independent embedded SHA literals")
    extractor = scanned[
        "historical/miner/2026-10-20-live-export/analysis/"
        "full_corpus_deep_discovery_v2/deep_extract.py"
    ]
    queries = []
    for node in ast.walk(extractor):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "safe_read_sql":
            continue
        table = next(
            (kw.value for kw in node.keywords if kw.arg == "table"), None
        )
        if (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                and isinstance(table, ast.Constant)
                and table.value == "cases"):
            queries.append(node.args[1].value)
    if queries != [CASE_QUERY]:
        raise DiscoveryLineageError(
            "Exact source-bound case-linkage SELECT missing or ambiguous"
        )
    return {
        "status": "ARCHIVED_ANALYSIS_FINGERPRINT_SOURCE_VERIFIED",
        "source_declared_discovery_database_sha256": DECLARED_DISCOVERY_SHA256,
        "source_declared_case_rows": DECLARED_CASES,
        "source_declared_case_linkage_sql_sha256": hashlib.sha256(
            CASE_QUERY.encode("utf-8")
        ).hexdigest(),
        "pinned_source_files_verified": len(scanned),
        "independent_embedded_database_hash_definitions": len(seen_shas),
        "recorded_sql_unit": "cases linkages (id,repo_id,issue_id,pr_id)",
        "actual_source_sqlite_snapshot_present": False,
        "original_3809_case_linkage_rows_reexecuted": False,
        "192_positive_workflows_reproduced": False,
        "455_mapped_changes_reproduced": False,
        "342_c_roots_reproduced": False,
    }


def replay_exact_case_query(
    conn: sqlite3.Connection, *,
    expected: int = DECLARED_CASES,
    query: str = CASE_QUERY,
) -> dict:
    # Supplying a smaller expected count is for synthetic unit tests only.
    if query != CASE_QUERY or type(expected) is not int or expected < 1:
        raise DiscoveryLineageError("Unapproved case-linkage SQL/denominator")
    rows = conn.execute(query).fetchall()
    if len(rows) != expected:
        raise DiscoveryLineageError(
            f"Observed {len(rows)} case-linkage rows, expected {expected}"
        )
    ids = [row[0] for row in rows]
    if len(set(ids)) != expected or any(
        value is None for row in rows for value in row
    ):
        raise DiscoveryLineageError("Case linkage has nulls/duplicate case IDs")
    return {
        "case_rows": len(rows),
        "unique_case_ids": len(set(ids)),
        "exact_source_case_linkage_sql": "REEXECUTED_READ_ONLY",
        "source_declared_expected_count": expected,
    }


def verify_source_locked_discovery_snapshot(
    database: Path, manifest: Path, *,
    root: Path = ROOT,
    integrity_deadline_seconds: float = 300.0,
) -> dict:
    source = archived_discovery_fingerprint(root)
    candidate = verify_candidate(
        database, manifest,
        integrity_deadline_seconds=integrity_deadline_seconds,
    )
    if (candidate["candidate_sha256"] !=
            source["source_declared_discovery_database_sha256"]):
        raise DiscoveryLineageError(
            "Candidate copy differs from the SHA embedded in three archived "
            "discovery source versions; cannot claim discovery-snapshot parity"
        )
    # Only after both the candidate byte gate and the source hash match can
    # even this small source-verified query run. No arbitrary SQL is accepted.
    path = database.absolute()
    conn = sqlite3.connect(
        path.as_uri() + "?mode=ro&immutable=1", uri=True, timeout=2.0
    )
    try:
        conn.enable_load_extension(False)
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA trusted_schema = OFF")
        observed = replay_exact_case_query(conn)
    finally:
        conn.close()
    return {
        "status": "PASS_SOURCE_LOCKED_DISCOVERY_CASE_QUERY_ONLY",
        "candidate_sha256": candidate["candidate_sha256"],
        "source_declared_discovery_database_sha256":
            source["source_declared_discovery_database_sha256"],
        "source_declared_case_query_sha256":
            source["source_declared_case_linkage_sql_sha256"],
        "observed": observed,
        "verified_scope": "Only discovery snapshot's cases linkage; not scanner cohort",
        "scanner_positive_192_reproduced": False,
        "mapped_producing_changes_455_reproduced": False,
        "roots_342_reproduced": False,
        "source_capture_and_original_qualifying_cohort_sql_verified": False,
        "source_derived_3809_workflow_unit_equality_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("audit-source", help="Check only original analysis SHA and query constants")
    verify = sub.add_parser(
        "verify-discovery-snapshot",
        help="Only for a source-SHA matching, approved local SQLite copy",
    )
    verify.add_argument("database", type=Path)
    verify.add_argument("private_manifest", type=Path)
    verify.add_argument("--integrity-seconds", type=float, default=300)
    args = parser.parse_args(argv)
    try:
        if args.command == "audit-source":
            report = archived_discovery_fingerprint()
            code = 0
        else:
            report = verify_source_locked_discovery_snapshot(
                args.database, args.private_manifest,
                integrity_deadline_seconds=args.integrity_seconds,
            )
            code = 0
    except (DiscoveryLineageError, SnapshotIntakeError, sqlite3.DatabaseError,
            OSError, TypeError, ValueError, SyntaxError) as exc:
        report = {
            "status": "BLOCKED_DISCOVERY_SOURCE_OR_DATA",
            "error": str(exc),
            "research_cohort_reproduced": False,
        }
        code = 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
