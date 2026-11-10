"""Transactional, memory-only fixture route for one miner issue/PR candidate.

NEW reconstruction adapter: not the original 3,000-line collection pipeline.
Reuses unchanged historical pure filters, marker logic, feature extraction and
base SQLite schema. All API data comes from ReplayGitHubClient fixtures.

The historical collector's lookback, repo-universe and JS/TS language-byte
screening are explicit opt-in decisions. Worker applicability, additional
historical collection modes, comment/commit fallbacks, cluster coordination,
and scanner routing remain outside this adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import re
import sqlite3
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from src.pipeline.collector_gates import (
    lookback_start_datetime, positive_lookback_months,
    repo_passes_universe, require_explicit_lookback_clock, within_lookback,
)
from src.pipeline.offline_repo_eligibility import evaluate_fixture_repo_eligibility

from src.filters.bot_filter import is_excluded_bot
from src.filters.issue_filters import passes_issue_filters
from src.filters.pr_filters import (
    classify_pr_files, enrich_files, has_javascript_typescript_surface,
    is_docs_scope_only,
)
from src.github.issue_linker import find_linked_issue_numbers
from src.github.replay_client import GitHubAPIError, ReplayGitHubClient
from src.markers.ai_markers import detect_ai_markers
from src.markers.upstream_features import extract_upstream_features

_REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_UPSTREAM_FLAGS = (
    "has_code_block", "has_inline_code", "has_traceback_or_log", "has_file_path",
    "has_function_or_class", "has_dependency_or_version", "has_suggested_fix",
    "has_ai_marker",
)


@dataclass(frozen=True)
class FixtureCollectionPolicy:
    """Explicit subset of the original PR→issue gates; not a production config."""

    exclude_bots: tuple[str, ...] = ()
    include_merged_prs: bool = True
    include_closed_unmerged_prs: bool = False
    require_javascript_typescript_surface: bool = False
    exclude_non_behaviour_only: bool = True
    exclude_docs_scope_only: bool = True
    max_changed_files_for_evidence: int = 75
    max_linked_issues_per_pr_for_evidence: int = 1
    issue_min_body_chars: int = 0
    require_issue_quality_filter: bool = False
    min_issue_words: int = 0
    english_only: bool = False
    ai_only: bool = False
    ai_marker_config: Mapping[str, Any] = field(default_factory=dict)
    # Newly isolated historical lookback and repo-screening decisions.
    # Defaults disabled to preserve the existing, explicitly partial fixture path.
    enforce_repo_universe: bool = False
    repo_min_stars: int = 200
    # Original JS/TS language-byte eligibility, backed by a memory-only
    # replay cache. This gate is separate from repo_universe.
    require_repo_js_ts_share: bool = False
    repo_eligibility_min_stars: int = 100
    repo_eligibility_min_js_ts_share: float = 0.50
    repo_eligibility_force_refresh: bool = False
    lookback_months: int | None = None
    lookback_start: str | None = None
    reference_now_utc: datetime | None = None
    require_pr_merged_after_lookback: bool = True
    require_issue_created_after_lookback: bool = True


@dataclass(frozen=True)
class FixtureCollectionOutcome:
    accepted: bool
    reason: str
    case_ids: tuple[int, ...] = ()
    issue_numbers: tuple[int, ...] = ()
    excluded_reasons: tuple[str, ...] = ()


def _require_memory_database(conn: sqlite3.Connection) -> None:
    if not isinstance(conn, sqlite3.Connection):
        raise TypeError("A sqlite3.Connection is required")
    attached = conn.execute("PRAGMA database_list").fetchall()
    if len(attached) != 1 or attached[0][1] != "main" or attached[0][2] != "":
        raise ValueError("This adapter refuses file-backed or attached databases")
    if int(conn.execute("PRAGMA foreign_keys").fetchone()[0]) != 1:
        raise ValueError("Expected SQLite foreign key enforcement")
    if conn.in_transaction:
        raise ValueError("Caller-owned open SQL transactions are not supported")


def _int_positive(value: Any, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a positive integer")
    try:
        number = int(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if number <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return number


def _url(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError(f"{name} must contain a fixture HTTPS URL")
    return value


def _one_exclusion(
    conn: sqlite3.Connection, repo_name: str, pr_number: int,
    reason: str, issue_number: int | None = None,
) -> FixtureCollectionOutcome:
    with conn:
        conn.execute(
            "INSERT INTO excluded_cases(repo, issue_number, pr_number, reason) VALUES (?,?,?,?)",
            (repo_name, issue_number, pr_number, reason),
        )
    return FixtureCollectionOutcome(False, reason, excluded_reasons=(reason,))


def _insert_repo(conn: sqlite3.Connection, repo: Mapping[str, Any]) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO repos(full_name,html_url,stars,language,archived) VALUES(?,?,?,?,?)",
        (repo["full_name"], repo["html_url"], repo.get("stargazers_count", 0),
         repo.get("language"), int(bool(repo.get("archived", False)))),
    )
    return int(conn.execute("SELECT id FROM repos WHERE full_name=?", (repo["full_name"],)).fetchone()[0])


def _upsert_pr(conn: sqlite3.Connection, repo_id: int, pr: Mapping[str, Any]) -> int:
    conn.execute(
        """INSERT INTO pull_requests(repo_id,number,url,title,body,author,state,merged,
           head_ref,base_ref,head_sha,base_sha,additions,deletions,changed_files_count,
           commits_count,review_comments_count,created_at,updated_at,closed_at,merged_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(repo_id,number) DO UPDATE SET
             title=excluded.title,body=excluded.body,state=excluded.state,
             merged=excluded.merged,head_ref=excluded.head_ref,
             base_ref=excluded.base_ref,head_sha=excluded.head_sha,base_sha=excluded.base_sha,
             additions=excluded.additions,deletions=excluded.deletions,
             changed_files_count=excluded.changed_files_count,
             commits_count=excluded.commits_count,
             review_comments_count=excluded.review_comments_count,
             updated_at=excluded.updated_at,closed_at=excluded.closed_at,
             merged_at=excluded.merged_at""",
        (repo_id, pr["number"], pr["html_url"], pr.get("title"), pr.get("body") or "",
         (pr.get("user") or {}).get("login"), pr.get("state"),
         int(pr.get("merged_at") is not None or bool(pr.get("merged", False))),
         (pr.get("head") or {}).get("ref"), (pr.get("base") or {}).get("ref"),
         (pr.get("head") or {}).get("sha"), (pr.get("base") or {}).get("sha"),
         pr.get("additions", 0), pr.get("deletions", 0), pr.get("changed_files", 0),
         pr.get("commits", 0), pr.get("review_comments", 0),
         pr.get("created_at"), pr.get("updated_at"), pr.get("closed_at"), pr.get("merged_at")),
    )
    return int(conn.execute(
        "SELECT id FROM pull_requests WHERE repo_id=? AND number=?",
        (repo_id, pr["number"]),
    ).fetchone()[0])


def _replace_pr_files(conn: sqlite3.Connection, pr_id: int, files: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM pr_files WHERE pr_id=?", (pr_id,))
    for item in files:
        conn.execute(
            "INSERT INTO pr_files(pr_id,filename,status,additions,deletions,patch,category) VALUES(?,?,?,?,?,?,?)",
            (pr_id, item.get("filename"), item.get("status"), item.get("additions", 0),
             item.get("deletions", 0), item.get("patch"), item.get("category")),
        )


def _upsert_issue(conn: sqlite3.Connection, repo_id: int, issue: Mapping[str, Any], word_count: int, is_english: bool) -> int:
    labels = json.dumps([x.get("name") if isinstance(x, dict) else str(x) for x in issue.get("labels", [])])
    conn.execute(
        """INSERT INTO issues(repo_id,github_id,number,url,title,body,author,state,
           labels,comments_count,created_at,updated_at,closed_at,word_count,is_english)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(repo_id,number) DO UPDATE SET
              title=excluded.title,body=excluded.body,state=excluded.state,
              labels=excluded.labels,comments_count=excluded.comments_count,
              updated_at=excluded.updated_at,closed_at=excluded.closed_at,
              word_count=excluded.word_count,is_english=excluded.is_english""",
        (repo_id, issue.get("id"), issue["number"], issue["html_url"],
         issue.get("title"), issue.get("body") or "",
         (issue.get("user") or {}).get("login"), issue.get("state"), labels,
         issue.get("comments", 0), issue.get("created_at"), issue.get("updated_at"),
         issue.get("closed_at"), word_count, int(is_english)),
    )
    return int(conn.execute("SELECT id FROM issues WHERE repo_id=? AND number=?",
                            (repo_id, issue["number"])).fetchone()[0])


def _write_upstream(conn: sqlite3.Connection, issue_id: int, features: dict[str, Any]) -> None:
    fields = "issue_id," + ",".join(_UPSTREAM_FLAGS) + ",feature_json"
    values = (issue_id,) + tuple(int(bool(features[name])) for name in _UPSTREAM_FLAGS) + (features["feature_json"],)
    placeholders = ",".join("?" for _ in values)
    updates = ",".join(f"{name}=excluded.{name}" for name in _UPSTREAM_FLAGS + ("feature_json",))
    conn.execute(
        f"INSERT INTO upstream_features({fields}) VALUES({placeholders}) "
        f"ON CONFLICT(issue_id) DO UPDATE SET {updates}",
        values,
    )


def _upsert_case(
    conn: sqlite3.Connection, repo_id: int, issue_id: int,
    pr_id: int, ai_cohort: str,
) -> int:
    conn.execute(
        """INSERT INTO cases(repo_id,issue_id,pr_id,ai_cohort,auto_tags,status)
           VALUES(?,?,?,?,?,'metadata_collected')
           ON CONFLICT(issue_id,pr_id) DO UPDATE SET
             ai_cohort=excluded.ai_cohort,auto_tags=excluded.auto_tags,
             updated_at=CURRENT_TIMESTAMP""",
        (repo_id, issue_id, pr_id, ai_cohort, json.dumps([ai_cohort])),
    )
    return int(conn.execute("SELECT id FROM cases WHERE issue_id=? AND pr_id=?",
                            (issue_id, pr_id)).fetchone()[0])


def collect_fixture_pr(
    conn: sqlite3.Connection,
    github: ReplayGitHubClient,
    repo: Mapping[str, Any],
    pr_number: int,
    *,
    policy: FixtureCollectionPolicy,
) -> FixtureCollectionOutcome:
    """Collect a fixture-backed PR into memory-only tables atomically.

    Missing API fixtures, unexpected HTTP errors and malformed responses raise
    rather than silently passing filters. The fixture replay is *not* a full
    historical cohort-construction implementation; see module docstring.
    """
    _require_memory_database(conn)
    if not isinstance(github, ReplayGitHubClient):
        raise TypeError("Only an explicit offline ReplayGitHubClient is accepted")
    if not isinstance(policy, FixtureCollectionPolicy):
        raise TypeError("Explicit FixtureCollectionPolicy required")
    if not isinstance(repo, Mapping):
        raise TypeError("repo must be mapping")
    name = str(repo.get("full_name") or "")
    if (not _REPO_NAME.fullmatch(name) or
            any(part in {".", ".."} for part in name.split("/"))):
        raise ValueError("repo full_name must be owner/name")
    _url(repo.get("html_url"), "repo.html_url")
    pr_num = _int_positive(pr_number, "pr_number")

    # Validate time controls before replay or database access. The original
    # code reads the wall clock for month-relative cutoff; injected time is
    # deliberately required here to make repeated fixture tests deterministic.
    months = positive_lookback_months(policy.lookback_months)
    start_date = lookback_start_datetime(policy.lookback_start)
    require_explicit_lookback_clock(
        months, start_date, reference_now_utc=policy.reference_now_utc,
    )
    if policy.enforce_repo_universe:
        included, reason = repo_passes_universe(
            repo, configured_min_stars=policy.repo_min_stars,
        )
        if not included:
            return _one_exclusion(conn, name, pr_num, reason)
    if policy.require_repo_js_ts_share:
        eligibility = evaluate_fixture_repo_eligibility(
            conn, github, name, repo_metadata=repo,
            min_stars=policy.repo_eligibility_min_stars,
            min_js_ts_share=policy.repo_eligibility_min_js_ts_share,
            force_refresh=policy.repo_eligibility_force_refresh,
        )
        if not eligibility["eligible"]:
            return _one_exclusion(
                conn, name, pr_num, f"repo_eligibility:{eligibility['reason']}",
            )

    pr = github.get(f"/repos/{name}/pulls/{pr_num}")
    if not isinstance(pr, dict) or _int_positive(pr.get("number"), "PR response number") != pr_num:
        raise ValueError("Fixture PR identity did not match requested PR")
    _url(pr.get("html_url"), "pr.html_url")
    # Matches historical _process_pr() ordering: lookback first, followed by
    # merged/unmerged settings and maintenance bot filtering.
    pr_date = (
        pr.get("merged_at")
        if policy.require_pr_merged_after_lookback
        else (pr.get("merged_at") or pr.get("closed_at")
              or pr.get("updated_at") or pr.get("created_at"))
    )
    if not within_lookback(
        pr_date, months=months, start=start_date,
        reference_now_utc=policy.reference_now_utc,
    ):
        return _one_exclusion(conn, name, pr_num, "outside_lookback_pr")
    merged = pr.get("merged_at") is not None or bool(pr.get("merged", False))
    if merged and not policy.include_merged_prs:
        return _one_exclusion(conn, name, pr_num, "merged_prs_disabled")
    if not merged and not policy.include_closed_unmerged_prs:
        return _one_exclusion(conn, name, pr_num, "unmerged_pr")
    if is_excluded_bot((pr.get("user") or {}).get("login"), pr.get("title"),
                       (pr.get("head") or {}).get("ref"), list(policy.exclude_bots)):
        return _one_exclusion(conn, name, pr_num, "bot_maintenance")

    try:
        files = enrich_files(list(github.paginate(
            f"/repos/{name}/pulls/{pr_num}/files", {"per_page": 100}
        )))
    except GitHubAPIError as exc:
        if exc.status_code in (404, 422):
            return _one_exclusion(conn, name, pr_num, "pr_files_unavailable")
        raise
    if policy.require_javascript_typescript_surface and not has_javascript_typescript_surface(files):
        return _one_exclusion(conn, name, pr_num, "no_javascript_typescript_surface")
    if policy.exclude_non_behaviour_only and classify_pr_files(files) == "non_behaviour_only":
        return _one_exclusion(conn, name, pr_num, "non_behaviour_only")
    if policy.exclude_docs_scope_only and is_docs_scope_only(files):
        return _one_exclusion(conn, name, pr_num, "docs_only_change")
    cap_files = int(policy.max_changed_files_for_evidence or 0)
    if cap_files > 0 and len(files) > cap_files:
        return _one_exclusion(conn, name, pr_num, "pr_scope_too_large_for_evidence")

    links = find_linked_issue_numbers(
        pr.get("title"), pr.get("body"), (pr.get("head") or {}).get("ref"), current_repo=name,
    )
    if not links:
        return _one_exclusion(conn, name, pr_num, "no_linked_issue")
    cap_links = int(policy.max_linked_issues_per_pr_for_evidence or 0)
    if cap_links > 0 and len(links) > cap_links:
        return _one_exclusion(conn, name, pr_num, "ambiguous_multi_issue_pr")

    valid = []
    exclusions = []
    for issue_number, method in links:
        try:
            issue = github.get(f"/repos/{name}/issues/{issue_number}")
        except GitHubAPIError as exc:
            if exc.status_code == 404:
                exclusions.append((issue_number, "stale_or_missing_issue_reference"))
                continue
            raise
        if not isinstance(issue, dict):
            raise ValueError("Issue fixture must be a JSON object")
        if _int_positive(issue.get("number"), "Issue response number") != issue_number:
            raise ValueError("Issue fixture identity does not match linked number")
        _url(issue.get("html_url"), "issue.html_url")
        issue_date = (
            issue.get("created_at")
            if policy.require_issue_created_after_lookback
            else (issue.get("closed_at") or issue.get("updated_at")
                  or issue.get("created_at"))
        )
        if not within_lookback(
            issue_date, months=months, start=start_date,
            reference_now_utc=policy.reference_now_utc,
        ):
            exclusions.append((issue_number, "outside_lookback_issue"))
            continue
        if "pull_request" in issue:
            exclusions.append((issue_number, "linked_item_is_pr"))
            continue
        if (policy.issue_min_body_chars and
            len((issue.get("body") or "").strip()) < policy.issue_min_body_chars):
            exclusions.append((issue_number, "issue_body_too_short"))
            continue
        min_words = policy.min_issue_words if policy.require_issue_quality_filter else 0
        english_only = policy.english_only if policy.require_issue_quality_filter else False
        accepted, meta = passes_issue_filters(issue, min_words, english_only)
        if not accepted:
            exclusions.append((issue_number, "issue_filter"))
            continue
        cohort, markers = detect_ai_markers({
            "issue_title": issue.get("title"), "issue_body": issue.get("body"),
            "pr_title": pr.get("title"), "pr_body": pr.get("body"),
            "pr_branch": (pr.get("head") or {}).get("ref"),
            "pr_author": (pr.get("user") or {}).get("login"),
            "commit_messages": "",  # no commit-message fallback in this subset
        }, dict(policy.ai_marker_config))
        if policy.ai_only and cohort == "AI-unknown":
            exclusions.append((issue_number, "ai_marker_required"))
            continue
        features = extract_upstream_features(issue.get("title"), issue.get("body"))
        features["has_ai_marker"] = cohort != "AI-unknown"
        valid.append((issue, method, meta, cohort, markers, features))

    case_ids: list[int] = []
    with conn:
        for issue_num, reason in exclusions:
            conn.execute(
                "INSERT INTO excluded_cases(repo,issue_number,pr_number,reason) VALUES(?,?,?,?)",
                (name, issue_num, pr_num, reason),
            )
        if valid:
            repo_id = _insert_repo(conn, repo)
            pr_id = _upsert_pr(conn, repo_id, pr)
            _replace_pr_files(conn, pr_id, files)
            for issue, method, meta, cohort, markers, features in valid:
                issue_id = _upsert_issue(conn, repo_id, issue, int(meta["word_count"]), bool(meta["is_english"]))
                conn.execute("INSERT OR IGNORE INTO issue_pr_links(issue_id,pr_id,method) VALUES(?,?,?)",
                             (issue_id, pr_id, method))
                _write_upstream(conn, issue_id, features)
                case_id = _upsert_case(conn, repo_id, issue_id, pr_id, cohort)
                # Intentional replay adapter difference: prevent duplicate marker rows
                # when a deterministic fixture is rerun. Original miner appends.
                conn.execute("DELETE FROM ai_markers WHERE case_id=?", (case_id,))
                for marker in markers:
                    conn.execute(
                        "INSERT INTO ai_markers(case_id,issue_id,pr_id,marker_text,marker_location,confidence,matched_tool) VALUES(?,?,?,?,?,?,?)",
                        (case_id, issue_id, pr_id, marker.marker_text, marker.marker_location,
                         marker.confidence, marker.matched_tool),
                    )
                case_ids.append(case_id)
    if not case_ids:
        reason = exclusions[0][1] if exclusions else "no_eligible_issue"
        return FixtureCollectionOutcome(False, reason,
                                        excluded_reasons=tuple(reason for _, reason in exclusions))
    return FixtureCollectionOutcome(
        True, "metadata_collected", tuple(case_ids),
        tuple(int(issue["number"]) for issue, *_ in valid),
        tuple(reason for _, reason in exclusions),
    )
