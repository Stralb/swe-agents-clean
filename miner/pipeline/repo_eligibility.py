from __future__ import annotations

import json
from typing import Any

from miner.db.database import Database


def ensure_repo_eligibility_schema(
    db: Database,
) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS repo_eligibility (
            repo_full_name TEXT PRIMARY KEY,
            stars INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            fork INTEGER DEFAULT 0,
            has_issues INTEGER DEFAULT 1,
            primary_language TEXT,
            language_bytes_json TEXT,
            total_language_bytes INTEGER DEFAULT 0,
            javascript_bytes INTEGER DEFAULT 0,
            typescript_bytes INTEGER DEFAULT 0,
            js_ts_bytes INTEGER DEFAULT 0,
            js_ts_share REAL DEFAULT 0.0,
            min_stars INTEGER DEFAULT 0,
            min_js_ts_share REAL DEFAULT 0.0,
            eligible INTEGER DEFAULT 0,
            reason TEXT,
            checked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    db.execute(
        """
        CREATE INDEX IF NOT EXISTS
            idx_repo_eligibility_eligible
        ON repo_eligibility(
            eligible,
            js_ts_share
        )
        """
    )


def _cached_result(
    row: dict[str, Any],
    repo_metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    repo = dict(repo_metadata or {})

    repo.setdefault(
        "full_name",
        row["repo_full_name"],
    )
    repo.setdefault(
        "stargazers_count",
        row["stars"],
    )
    repo.setdefault(
        "archived",
        bool(row["archived"]),
    )
    repo.setdefault(
        "fork",
        bool(row["fork"]),
    )
    repo.setdefault(
        "has_issues",
        bool(row["has_issues"]),
    )
    repo.setdefault(
        "language",
        row["primary_language"],
    )

    try:
        language_bytes = json.loads(
            row.get("language_bytes_json")
            or "{}"
        )
    except Exception:
        language_bytes = {}

    return {
        "repo": repo,
        "eligible": bool(row["eligible"]),
        "reason": row.get("reason") or "",
        "stars": int(row.get("stars") or 0),
        "language_bytes": language_bytes,
        "total_language_bytes": int(
            row.get("total_language_bytes")
            or 0
        ),
        "javascript_bytes": int(
            row.get("javascript_bytes")
            or 0
        ),
        "typescript_bytes": int(
            row.get("typescript_bytes")
            or 0
        ),
        "js_ts_bytes": int(
            row.get("js_ts_bytes")
            or 0
        ),
        "js_ts_share": float(
            row.get("js_ts_share")
            or 0.0
        ),
        "cached": True,
    }


def evaluate_repo_eligibility(
    db: Database,
    gh: Any,
    full_name: str,
    *,
    repo_metadata: dict[str, Any] | None = None,
    min_stars: int = 100,
    min_js_ts_share: float = 0.50,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Evaluate and cache the repository-level JS/TS study gate.

    The denominator is GitHub Linguist's total language bytes.
    JavaScript and TypeScript bytes are combined because TypeScript
    belongs to the JavaScript ecosystem and is analysed by the same
    CodeQL language extractor.

    This is a repository eligibility gate, not a security-risk label.
    """

    ensure_repo_eligibility_schema(db)

    normalized_name = str(full_name).strip()

    cached = db.one(
        """
        SELECT *
        FROM repo_eligibility
        WHERE lower(repo_full_name) =
              lower(?)
          AND min_stars = ?
          AND abs(
                  min_js_ts_share - ?
              ) < 0.0000001
        """,
        (
            normalized_name,
            int(min_stars),
            float(min_js_ts_share),
        ),
    )

    if cached and not force_refresh:
        return _cached_result(
            cached,
            repo_metadata,
        )

    repo = dict(
        repo_metadata
        or gh.get(
            "/repos/%s"
            % normalized_name
        )
        or {}
    )

    languages_raw = (
        gh.get(
            "/repos/%s/languages"
            % normalized_name
        )
        or {}
    )

    language_bytes = {
        str(language): int(value or 0)
        for language, value
        in dict(languages_raw).items()
        if int(value or 0) >= 0
    }

    total_bytes = sum(
        language_bytes.values()
    )

    javascript_bytes = int(
        language_bytes.get(
            "JavaScript",
            0,
        )
    )

    typescript_bytes = int(
        language_bytes.get(
            "TypeScript",
            0,
        )
    )

    js_ts_bytes = (
        javascript_bytes
        + typescript_bytes
    )

    js_ts_share = (
        js_ts_bytes / total_bytes
        if total_bytes > 0
        else 0.0
    )

    stars = int(
        repo.get("stargazers_count")
        or repo.get("stars")
        or 0
    )

    archived = bool(
        repo.get("archived")
    )

    fork = bool(
        repo.get("fork")
    )

    has_issues = bool(
        repo.get(
            "has_issues",
            True,
        )
    )

    if archived:
        eligible = False
        reason = "archived"
    elif fork:
        eligible = False
        reason = "fork"
    elif not has_issues:
        eligible = False
        reason = "issues_disabled"
    elif stars < int(min_stars):
        eligible = False
        reason = (
            "stars_below_%s"
            % int(min_stars)
        )
    elif total_bytes <= 0:
        eligible = False
        reason = "no_language_bytes"
    elif js_ts_share < float(
        min_js_ts_share
    ):
        eligible = False
        reason = (
            "js_ts_share_below_%.4f"
            % float(min_js_ts_share)
        )
    else:
        eligible = True
        reason = "eligible"

    db.execute(
        """
        INSERT INTO repo_eligibility(
            repo_full_name,
            stars,
            archived,
            fork,
            has_issues,
            primary_language,
            language_bytes_json,
            total_language_bytes,
            javascript_bytes,
            typescript_bytes,
            js_ts_bytes,
            js_ts_share,
            min_stars,
            min_js_ts_share,
            eligible,
            reason,
            checked_at
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            CURRENT_TIMESTAMP
        )
        ON CONFLICT(repo_full_name)
        DO UPDATE SET
            stars=excluded.stars,
            archived=excluded.archived,
            fork=excluded.fork,
            has_issues=excluded.has_issues,
            primary_language=
                excluded.primary_language,
            language_bytes_json=
                excluded.language_bytes_json,
            total_language_bytes=
                excluded.total_language_bytes,
            javascript_bytes=
                excluded.javascript_bytes,
            typescript_bytes=
                excluded.typescript_bytes,
            js_ts_bytes=
                excluded.js_ts_bytes,
            js_ts_share=
                excluded.js_ts_share,
            min_stars=
                excluded.min_stars,
            min_js_ts_share=
                excluded.min_js_ts_share,
            eligible=
                excluded.eligible,
            reason=
                excluded.reason,
            checked_at=
                CURRENT_TIMESTAMP
        """,
        (
            normalized_name,
            stars,
            int(archived),
            int(fork),
            int(has_issues),
            repo.get("language"),
            json.dumps(
                language_bytes,
                sort_keys=True,
            ),
            total_bytes,
            javascript_bytes,
            typescript_bytes,
            js_ts_bytes,
            js_ts_share,
            int(min_stars),
            float(min_js_ts_share),
            int(eligible),
            reason,
        ),
    )

    return {
        "repo": repo,
        "eligible": eligible,
        "reason": reason,
        "stars": stars,
        "language_bytes": language_bytes,
        "total_language_bytes": total_bytes,
        "javascript_bytes": javascript_bytes,
        "typescript_bytes": typescript_bytes,
        "js_ts_bytes": js_ts_bytes,
        "js_ts_share": js_ts_share,
        "cached": False,
    }
