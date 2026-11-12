"""Fixture-backed reconstruction of the original JS/TS repo eligibility cache.

Uses the archived *base* SQLite schema and an explicit in-memory GitHub replay
client. Historical src/pipeline/repo_eligibility.py and src/db/database.py are
preserved unchanged. No real network or filesystem-backed database is possible.
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping
from typing import Any

from src.github.replay_client import ReplayGitHubClient

_REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_FIELDS = (
    "repo_full_name", "stars", "archived", "fork", "has_issues",
    "primary_language", "language_bytes_json", "total_language_bytes",
    "javascript_bytes", "typescript_bytes", "js_ts_bytes", "js_ts_share",
    "min_stars", "min_js_ts_share", "eligible", "reason",
)
_FIELDS_UPDATE = tuple(name for name in _FIELDS if name != "repo_full_name")


def _require_in_memory(conn: sqlite3.Connection) -> None:
    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("An explicit SQLite connection is required")
    entries = conn.execute("PRAGMA database_list").fetchall()
    if len(entries) != 1 or entries[0][1] != "main" or entries[0][2] != "":
        raise ValueError("Refusing file-backed or attached SQLite databases")
    if int(conn.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
        raise ValueError("Foreign keys must be enabled")
    if conn.in_transaction:
        raise ValueError("A pre-existing transaction is not supported")


def _from_cached_row(row: sqlite3.Row, metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Mirror archived _cached_result(). Caller-provided metadata is not refreshed."""
    record = dict(row)
    repo = dict(metadata or {})
    for key, col in (
        ("full_name", "repo_full_name"),
        ("stargazers_count", "stars"),
        ("archived", "archived"),
        ("fork", "fork"),
        ("has_issues", "has_issues"),
        ("language", "primary_language"),
    ):
        value = record[col]
        if key in {"archived", "fork", "has_issues"}:
            value = bool(value)
        repo.setdefault(key, value)
    try:
        langs = json.loads(record.get("language_bytes_json") or "{}")
    except (TypeError, ValueError):
        langs = {}
    return {
        "repo": repo,
        "eligible": bool(record["eligible"]),
        "reason": record.get("reason") or "",
        "stars": int(record.get("stars") or 0),
        "language_bytes": langs,
        "total_language_bytes": int(record.get("total_language_bytes") or 0),
        "javascript_bytes": int(record.get("javascript_bytes") or 0),
        "typescript_bytes": int(record.get("typescript_bytes") or 0),
        "js_ts_bytes": int(record.get("js_ts_bytes") or 0),
        "js_ts_share": float(record.get("js_ts_share") or 0.0),
        "cached": True,
    }


def evaluate_fixture_repo_eligibility(
    conn: sqlite3.Connection,
    github: ReplayGitHubClient,
    full_name: str,
    *,
    repo_metadata: Mapping[str, Any] | None = None,
    min_stars: int = 100,
    min_js_ts_share: float = 0.50,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Mirror the original eligibility decision/cache using only memory fixtures.

    Cache identity mirrors archived source: normalized name (case-insensitive),
    matching min_stars, and epsilon 1e-7 for min_js_ts_share. The single-row
    primary key still stores only the *latest* threshold per repository.
    """
    _require_in_memory(conn)
    if not isinstance(github, ReplayGitHubClient):
        raise TypeError("An offline ReplayGitHubClient is required")
    name = str(full_name).strip()
    if (_REPO_NAME.fullmatch(name) is None
            or any(part in {".", ".."} for part in name.split("/"))):
        raise ValueError("Repository name must be owner/name")
    threshold_stars = int(min_stars)
    threshold_share = float(min_js_ts_share)

    cached = conn.execute(
        """SELECT * FROM repo_eligibility
           WHERE lower(repo_full_name)=lower(?)
             AND min_stars=?
             AND abs(min_js_ts_share - ?) < 0.0000001""",
        (name, threshold_stars, threshold_share),
    ).fetchone()
    if cached is not None and not force_refresh:
        return _from_cached_row(cached, repo_metadata)

    if repo_metadata is not None and not isinstance(repo_metadata, Mapping):
        raise TypeError("repo_metadata must be a mapping")
    if repo_metadata:
        repo = dict(repo_metadata)
    else:
        fetched = github.get(f"/repos/{name}")
        if not isinstance(fetched, dict):
            raise ValueError("Repository fixture must be a JSON object")
        repo = dict(fetched)
    lang_payload = github.get(f"/repos/{name}/languages")
    if not isinstance(lang_payload, Mapping):
        raise ValueError("Language-byte fixture must be a mapping")

    language_bytes = {
        str(language): int(value or 0)
        for language, value in lang_payload.items()
        if int(value or 0) >= 0
    }
    total = sum(language_bytes.values())
    js = int(language_bytes.get("JavaScript", 0))
    ts = int(language_bytes.get("TypeScript", 0))
    share = (js + ts) / total if total > 0 else 0.0
    stars = int(repo.get("stargazers_count") or repo.get("stars") or 0)
    archived = bool(repo.get("archived"))
    fork = bool(repo.get("fork"))
    has_issues = bool(repo.get("has_issues", True))

    if archived:
        eligible, reason = False, "archived"
    elif fork:
        eligible, reason = False, "fork"
    elif not has_issues:
        eligible, reason = False, "issues_disabled"
    elif stars < threshold_stars:
        eligible, reason = False, f"stars_below_{threshold_stars}"
    elif total <= 0:
        eligible, reason = False, "no_language_bytes"
    elif share < threshold_share:
        eligible, reason = False, f"js_ts_share_below_{threshold_share:.4f}"
    else:
        eligible, reason = True, "eligible"

    values = (
        name, stars, int(archived), int(fork), int(has_issues),
        repo.get("language"), json.dumps(language_bytes, sort_keys=True),
        total, js, ts, js + ts, share, threshold_stars,
        threshold_share, int(eligible), reason,
    )
    cols = ",".join(_FIELDS)
    placeholders = ",".join("?" for _ in _FIELDS)
    updates = ",".join(f"{key}=excluded.{key}" for key in _FIELDS_UPDATE)
    with conn:
        conn.execute(
            f"INSERT INTO repo_eligibility({cols},checked_at) "
            f"VALUES({placeholders},CURRENT_TIMESTAMP) "
            f"ON CONFLICT(repo_full_name) DO UPDATE SET "
            f"{updates},checked_at=CURRENT_TIMESTAMP",
            values,
        )

    return {
        "repo": repo,
        "eligible": eligible,
        "reason": reason,
        "stars": stars,
        "language_bytes": language_bytes,
        "total_language_bytes": total,
        "javascript_bytes": js,
        "typescript_bytes": ts,
        "js_ts_bytes": js + ts,
        "js_ts_share": share,
        "cached": False,
    }
