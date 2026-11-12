from __future__ import annotations

import logging
import math
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from src.db.database import Database
from src.filters.bot_filter import is_excluded_bot
from src.filters.issue_filters import passes_issue_filters
from src.filters.pr_filters import has_javascript_typescript_surface
from src.filters.pr_filters import classify_pr_files, enrich_files, is_docs_scope_only
from src.filters.tool_applicability import (
    has_any_applicable_downstream_worker,
    has_primary_applicable_downstream_worker,
    has_high_yield_downstream_surface,
    high_yield_surface_reasons,
    route_reasons,
)
from src.github.client import GitHubAPIError, GitHubClient, GitHubSecondaryRateLimit
from src.github.issue_linker import find_linked_issue_numbers
from src.markers.ai_markers import detect_ai_markers
from src.markers.upstream_features import extract_upstream_features
from src.settings import Settings
from src.pipeline.agentic_discovery import build_agentic_query_jobs, validate_pr_for_job
from src.pipeline.repo_eligibility import evaluate_repo_eligibility
from src.pipeline.existing_repo_seed import load_existing_repo_seed_names
from src.pipeline.repo_universe import global_active_pr_query, lookback_window, month_windows, repo_month_pr_query, repo_window_pr_query, shard_accept, star_band_queries

log = logging.getLogger(__name__)


LOOKBACK_START_DATE = '2025-01-01'
TARGETED_ISSUE_LINK_TERMS = ('"fixes #"', '"closes #"', '"resolves #"')

# High-precision default streams. Broad one-word recall terms are intentionally
# excluded from the default live run because they caused noisy GitHub hits and
# poor conversion into same-repo issue-linked, behaviour-changing cases.
TARGETED_STREAMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ai_agents",
        (
            '"Claude Code"',
            '"Co-Authored-By: Claude"',
            '"Codex"',
            '"OpenAI Codex"',
            '"GitHub Copilot"',
            '"copilot"',
            '"cursor"',
            '"aider"',
            '"devin"',
            '"openhands"',
            '"ai-generated"',
        ),
    ),
    (
        "dependency",
        (
            '"requirements.txt"',
            '"pyproject.toml"',
            '"poetry.lock"',
            '"Pipfile.lock"',
            '"package.json"',
            '"package-lock.json"',
            '"yarn.lock"',
            '"pnpm-lock.yaml"',
            '"go.mod"',
            '"go.sum"',
            '"pom.xml"',
            '"build.gradle"',
            '"build.gradle.kts"',
            '"Cargo.toml"',
            '"Cargo.lock"',
            '"composer.json"',
            '"composer.lock"',
        ),
    ),
    (
        "ci_cd_secrets",
        (
            '".github/workflows"',
            '"pull_request_target"',
            '"permissions:"',
            '"GITHUB_TOKEN"',
            '"secrets."',
            '".env"',
        ),
    ),
    (
        "source_security",
        (
            '"shell=True"',
            '"os.system"',
            '"subprocess"',
            '"eval("',
            '"exec("',
            '"pickle"',
            '"yaml.load"',
        ),
    ),
    (
        "issue_steering",
        (
            '"steps to reproduce"',
            '"minimal repro"',
            '"stack trace"',
            '"traceback"',
        ),
    ),
    (
        "security_regression",
        (
            '"CVE"',
            '"security fix"',
            '"security regression"',
            '"revert security"',
        ),
    ),
)

SINGLE_STREAM_HIGH_SIGNAL_TERMS = {
    '"Claude Code"', '"Co-Authored-By: Claude"', '"Codex"', '"OpenAI Codex"',
    '"GitHub Copilot"', '"Devin"', '"Cursor"', '"OpenHands"', '"Aider"',
    '"requirements.txt"', '"pyproject.toml"', '"poetry.lock"', '"Pipfile.lock"',
    '".github/workflows"', '"pull_request_target"', '"GITHUB_TOKEN"', '"secrets."',
    '"shell=True"', '"os.system"', '"eval("', '"exec("', '"pickle.load"', '"yaml.load"',
    '"CVE"', '"security regression"', '"revert security"',
}


def _targeted_base_query(settings: Settings | None = None) -> str:
    cfg = settings.config if settings is not None else {}
    github_cfg = cfg.get("github", {}) if isinstance(cfg, dict) else {}
    collection_cfg = cfg.get("collection", {}) if isinstance(cfg, dict) else {}
    min_stars = int(github_cfg.get("min_stars", collection_cfg.get("min_stars", 200)) or 200)
    language = str(github_cfg.get("language", "Python") or "Python")
    lookback = str(collection_cfg.get("lookback_start", LOOKBACK_START_DATE) or LOOKBACK_START_DATE)
    return f'is:pr is:merged language:{language} stars:>={min_stars} archived:false merged:>={lookback} in:title,body'


# Backwards-compatible constant for tests/UI helpers; runtime uses _targeted_base_query(settings).
TARGETED_BASE_QUERY = _targeted_base_query(None)


def _targeted_queries_for_term(stream_key: str, term: str, settings: Settings | None = None, phase: str = "combined_issue_link_stream") -> list[str]:
    base = _targeted_base_query(settings)
    if phase == "issue_link_baseline":
        return [f"{base} {term}"] if term in TARGETED_ISSUE_LINK_TERMS else []
    if phase == "single_stream":
        return [f"{base} {term}"]
    return [f"{base} {link_term} {term}" for link_term in TARGETED_ISSUE_LINK_TERMS]


def _interleave_by_stream(groups: dict[str, list[tuple[str, str, str]]]) -> list[tuple[str, str, str]]:
    """Round-robin query jobs so one stream/repo class cannot dominate a pass."""
    out: list[tuple[str, str, str]] = []
    keys = list(groups.keys())
    max_len = max((len(v) for v in groups.values()), default=0)
    for idx in range(max_len):
        for key in keys:
            jobs = groups.get(key) or []
            if idx < len(jobs):
                out.append(jobs[idx])
    return out



def _term_allowed_for_language(term: str, settings: Settings | None = None) -> bool:
    """Avoid wasting GitHub Search quota on language-mismatched evidence terms."""
    cfg = settings.config if settings is not None else {}
    github_cfg = cfg.get("github", {}) if isinstance(cfg, dict) else {}
    lang = str(github_cfg.get("language", "Python") or "Python").lower()
    t = (term or "").lower()

    python_only = {
        '"requirements.txt"', '"pyproject.toml"', '"poetry.lock"', '"pipfile.lock"',
        '"setup.py"', '"setup.cfg"', '"shell=true"', '"os.system"', '"pickle.load"',
        '"yaml.load"', '"traceback"',
    }

    js_only = {
        '"package.json"', '"package-lock.json"', '"yarn.lock"', '"pnpm-lock.yaml"',
        '"npm"', '"node"', '"typescript"', '"javascript"',
    }

    common = {
        '"claude code"', '"co-authored-by: claude"', '"codex"', '"openai codex"',
        '"github copilot"', '"copilot"', '"devin"', '"cursor"', '"openhands"',
        '"aider"', '"ai-generated"', '"agent-generated"',
        '".github/workflows"', '"pull_request_target"', '"permissions:"', '"github_token"',
        '"actions_id_token_request_token"', '"id-token"', '"secrets."', '"workflow_dispatch"',
        '"actions/github-script"', '"printenv"', '"echo $"',
        '"eval("', '"exec("', '"deserialize"', '"sql injection"', '"path traversal"',
        '"ssrf"', '"verify=false"', '"disable validation"', '"bypass validation"',
        '"skip verification"', '"steps to reproduce"', '"minimal repro"', '"stack trace"',
        '"expected behavior"', '"actual behavior"', '"failing test"', '"regression test"',
        '"cve"', '"security fix"', '"security regression"', '"revert security"',
        '"disable check"', '"bypass"', '"too strict"', '"false positive"',
        '"downgrade"', '"relax constraint"', '"version conflict"', '"dependency conflict"',
        '"pin version"', '"unpin"',
    }

    if lang in {"javascript", "typescript"}:
        return t not in python_only
    if lang == "python":
        return t not in js_only
    return True


def _targeted_query_jobs(settings: Settings) -> list[tuple[str, str, str]]:
    cfg = settings.config
    retrieval_cfg = cfg.get("retrieval", {}) or {}
    phases = retrieval_cfg.get("query_phases") or cfg.get("collection", {}).get("query_phases") or [
        "issue_link_baseline",
        "combined_issue_link_stream",
        "single_stream_high_signal",
    ]
    if isinstance(phases, str):
        phases = [p.strip() for p in phases.split(",") if p.strip()]

    jobs: list[tuple[str, str, str]] = []
    for phase in phases:
        if phase == "issue_link_baseline":
            for term in TARGETED_ISSUE_LINK_TERMS:
                for q in _targeted_queries_for_term("issue_links", term, settings, phase=phase):
                    jobs.append(("issue_links", term, q))
            continue

        groups: dict[str, list[tuple[str, str, str]]] = {}
        for stream_key, stream_terms in TARGETED_STREAMS:
            groups.setdefault(stream_key, [])
            for term in stream_terms:
                if not _term_allowed_for_language(term, settings):
                    continue
                if phase == "single_stream_high_signal" and term not in SINGLE_STREAM_HIGH_SIGNAL_TERMS:
                    continue
                actual_phase = "single_stream" if phase == "single_stream_high_signal" else phase
                for q in _targeted_queries_for_term(stream_key, term, settings, phase=actual_phase):
                    groups[stream_key].append((stream_key, term, q))
        jobs.extend(_interleave_by_stream(groups))
    return jobs

def _record_case_retrieval(db: Database, case_id: int, stream_key: str, term: str, final_query: str) -> None:
    db.execute(
        """
        INSERT INTO retrieval_queries(stream_key, term, final_query, status, last_run_at)
        VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP)
        ON CONFLICT(final_query) DO UPDATE SET last_run_at=CURRENT_TIMESTAMP, status='running'
        """,
        (stream_key, term, final_query),
    )
    db.execute(
        """
        INSERT OR IGNORE INTO case_retrievals(case_id, stream_key, term, final_query)
        VALUES (?, ?, ?, ?)
        """,
        (case_id, stream_key, term, final_query),
    )


def _pipeline_event(db: Database, event_type: str, detail: str) -> None:
    try:
        db.execute(
            "INSERT INTO pipeline_events(event_type, detail) VALUES (?, ?)",
            (event_type, detail[:2000]),
        )
    except Exception:
        log.debug("Could not record pipeline event %s", event_type, exc_info=True)


def _case_ids_for_pr(db: Database, repo_full_name: str, pr_num: int) -> list[int]:
    rows = db.query(
        """
        SELECT c.id
        FROM cases c
        JOIN repos r ON c.repo_id=r.id
        JOIN pull_requests p ON c.pr_id=p.id
        WHERE r.full_name=? AND p.number=?
        """,
        (repo_full_name, pr_num),
    )
    return [int(r["id"]) for r in rows]




def _known_pr_outcomes(db: Database, repo_full_name: str, pr_num: int) -> dict[str, int]:
    """Return existing visible outcomes for a PR already seen in the DB.

    This makes retrieval accounting honest across process restarts. A PR that
    was already made into a case or explicit exclusion must not be treated as
    new work, but it must still be counted as an accounted duplicate/outcome.
    """
    case_rows = db.query(
        """
        SELECT c.id
        FROM cases c
        JOIN repos r ON c.repo_id=r.id
        JOIN pull_requests p ON c.pr_id=p.id
        WHERE r.full_name=? AND p.number=?
        """,
        (repo_full_name, pr_num),
    )
    excl_rows = db.query(
        """
        SELECT id
        FROM excluded_cases
        WHERE repo=? AND pr_number=?
        """,
        (repo_full_name, pr_num),
    )
    pr_rows = db.query(
        """
        SELECT p.id
        FROM pull_requests p
        JOIN repos r ON p.repo_id=r.id
        WHERE r.full_name=? AND p.number=?
        """,
        (repo_full_name, pr_num),
    )
    return {"cases": len(case_rows), "exclusions": len(excl_rows), "prs": len(pr_rows)}

def _repo_visible_outcome_count(db: Database, repo_full_name: str) -> int:
    """Cases plus explicit exclusions for a repo, used to keep retrieval wide-first."""
    row = db.one(
        """
        SELECT
          (SELECT COUNT(*) FROM cases c JOIN repos r ON c.repo_id=r.id WHERE r.full_name=?) +
          (SELECT COUNT(*) FROM excluded_cases WHERE repo=?) AS n
        """,
        (repo_full_name, repo_full_name),
    ) or {"n": 0}
    return int(row.get("n") or 0)


def _sample_strategy(settings: Settings, key: str, default: str = "none") -> str:
    return str(settings.config.get("collection", {}).get(key, default)).strip().lower()


def _random_seed(settings: Settings) -> int:
    try:
        return int(settings.config.get("collection", {}).get("random_seed", 42))
    except (TypeError, ValueError):
        return 42


def _pool_multiplier(settings: Settings, key: str, default: int = 3) -> int:
    try:
        return max(1, int(settings.config.get("collection", {}).get(key, default)))
    except (TypeError, ValueError):
        return default


def _stable_shuffle(items: list[Any], seed: int, salt: str) -> list[Any]:
    shuffled = list(items)
    rng = random.Random(f"{seed}:{salt}")
    rng.shuffle(shuffled)
    return shuffled


def _lookback_months(settings: Settings) -> int | None:
    value = settings.config.get("collection", {}).get("lookback_months")
    try:
        months = int(value)
    except (TypeError, ValueError):
        return None
    return months if months > 0 else None


def _lookback_start(settings: Settings) -> datetime | None:
    value = settings.config.get("collection", {}).get("lookback_start")
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        log.warning("Ignoring invalid collection.lookback_start=%r", value)
        return None


def _iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _within_lookback(value: str | None, months: int | None, start_date: datetime | None = None) -> bool:
    dt = _iso_dt(value)
    if dt is None:
        return True
    if start_date is not None:
        return dt.timestamp() >= start_date.timestamp()
    if not months:
        return True
    cutoff = datetime.now(timezone.utc).timestamp() - months * 31 * 24 * 60 * 60
    return dt.timestamp() >= cutoff


def _lookback_description(months: int | None, start_date: datetime | None = None) -> str:
    if start_date is not None:
        return f"since {start_date.date().isoformat()}"
    if months:
        return f"outside {months}-month lookback"
    return "outside configured lookback"


def _min_issue_body_chars(settings: Settings) -> int:
    cfg = settings.config
    raw = cfg.get("filters", {}).get("issue_min_body_chars", cfg.get("collection", {}).get("issue_min_body_chars", 200))
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 200


def _issue_body_char_count(issue: dict[str, Any]) -> int:
    return len((issue.get("body") or "").strip())



def _limit_reached(start: float, settings: Settings, repo_count: int, case_count: int) -> bool:
    lim = settings.limits
    if lim.max_seconds and time.time() - start >= lim.max_seconds:
        return True
    if lim.max_repos and repo_count >= lim.max_repos:
        return True
    if lim.max_cases and case_count >= lim.max_cases:
        return True
    return False


def _store_upstream_features(db: Database, issue_id: int, features: dict) -> None:
    db.execute(
        """
        INSERT INTO upstream_features(issue_id, has_code_block, has_inline_code, has_traceback_or_log, has_file_path,
            has_function_or_class, has_dependency_or_version, has_suggested_fix, has_ai_marker, feature_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(issue_id) DO UPDATE SET
            has_code_block=excluded.has_code_block,
            has_inline_code=excluded.has_inline_code,
            has_traceback_or_log=excluded.has_traceback_or_log,
            has_file_path=excluded.has_file_path,
            has_function_or_class=excluded.has_function_or_class,
            has_dependency_or_version=excluded.has_dependency_or_version,
            has_suggested_fix=excluded.has_suggested_fix,
            has_ai_marker=excluded.has_ai_marker,
            feature_json=excluded.feature_json
        """,
        (
            issue_id,
            int(features["has_code_block"]),
            int(features["has_inline_code"]),
            int(features["has_traceback_or_log"]),
            int(features["has_file_path"]),
            int(features["has_function_or_class"]),
            int(features["has_dependency_or_version"]),
            int(features["has_suggested_fix"]),
            int(features.get("has_ai_marker", False)),
            features["feature_json"],
        ),
    )


def _repo_full_name_from_url(repository_url: str) -> str:
    return repository_url.replace("https://api.github.com/repos/", "", 1)



PR_HYDRATION_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    pullRequest(number: $number) {
      number
      merged
      mergedAt
      author { login }
      mergeCommit { oid }
      files(first: 100) {
        nodes { path additions deletions changeType }
        pageInfo { hasNextPage }
      }
      closingIssuesReferences(first: 20) {
        nodes {
          number
          url
          repository { nameWithOwner }
        }
      }
    }
  }
}
"""


def _graphql_hydrate_pr(gh: GitHubClient, full_name: str, pr_num: int, enabled: bool = True) -> dict[str, Any] | None:
    if not enabled or not hasattr(gh, "graphql"):
        return None
    try:
        owner, name = full_name.split("/", 1)
        data = gh.graphql(PR_HYDRATION_QUERY, {"owner": owner, "name": name, "number": int(pr_num)})
        repo = (((data or {}).get("data") or {}).get("repository") or {})
        pr = repo.get("pullRequest") or {}
        if not pr:
            return None
        return {
            "repo": repo.get("nameWithOwner") or full_name,
            "pr_number": pr.get("number") or pr_num,
            "merged": bool(pr.get("merged")),
            "merged_at": pr.get("mergedAt"),
            "merge_commit_sha": ((pr.get("mergeCommit") or {}).get("oid")),
            "files": list(((pr.get("files") or {}).get("nodes") or [])),
            "files_has_next_page": bool((((pr.get("files") or {}).get("pageInfo") or {}).get("hasNextPage"))),
            "closing_issues": list(((pr.get("closingIssuesReferences") or {}).get("nodes") or [])),
        }
    except Exception as exc:
        log.debug("GraphQL PR hydration failed for %s#%s: %s", full_name, pr_num, exc)
        return None


def _same_repo_graphql_issue_links(hydration: dict[str, Any] | None, full_name: str) -> list[tuple[int, str]]:
    if not hydration:
        return []
    links: list[tuple[int, str]] = []
    for issue in hydration.get("closing_issues") or []:
        repo = ((issue.get("repository") or {}).get("nameWithOwner") or "")
        if repo.lower() == full_name.lower() and issue.get("number"):
            links.append((int(issue["number"]), "graphql-closing-issue"))
    return links

def _safe_commit_messages(gh: GitHubClient, full_name: str, pr_num: int, enabled: bool, max_messages: int = 30) -> str:
    if not enabled:
        return ""
    messages: list[str] = []
    try:
        for idx, commit in enumerate(gh.paginate(f"/repos/{full_name}/pulls/{pr_num}/commits", {"per_page": 100}, max_pages=1)):
            if idx >= max_messages:
                break
            msg = ((commit.get("commit") or {}).get("message") or "").strip()
            if msg:
                messages.append(msg)
    except Exception as e:
        log.debug("Could not fetch commit messages for %s PR #%s: %s", full_name, pr_num, e)
    return "\n---commit---\n".join(messages)


def _search_terms(cfg: dict[str, Any]) -> list[str]:
    """Return AI search terms based on the configured profile.

    high     = strongest provenance strings only; least biased/noisy and safest for GitHub search limits.
    balanced = high + specific agent/product phrases.
    broad    = high + all configured medium terms, including generic AI wording.
    """
    ai_cfg = cfg.get("ai_markers", {})
    ai_search = cfg.get("collection", {}).get("ai_search", {}) or {}
    profile = str(ai_search.get("profile", "high")).lower()

    high_terms = [str(v).strip() for v in (ai_cfg.get("high_confidence", []) or []) if str(v).strip()]
    medium_terms = [str(v).strip() for v in (ai_cfg.get("medium_confidence", []) or []) if str(v).strip()]

    if profile == "high":
        terms = high_terms
    elif profile == "balanced":
        specific = {
            "claude code",
            "copilot agent",
            "copilot workspace",
            "cursor agent",
            "cursor deep agent",
            "devin",
            "openhands",
            "opendevin",
            "cline",
            "jules",
            "genie",
            "windsurf",
        }
        terms = high_terms + [t for t in medium_terms if t.lower() in specific]
    else:
        terms = high_terms + medium_terms

    # Avoid very generic phrases unless explicitly using broad mode.
    generic = {"generated with", "generated by ai", "ai-generated", "agent-generated", "llm-generated", "codex", "chatgpt"}
    if profile != "broad":
        terms = [t for t in terms if t.lower() not in generic]

    seen = set()
    out = []
    for t in terms:
        key = t.lower()
        if key not in seen and len(t) >= 4:
            seen.add(key)
            out.append(t)
    return out

def _quote(term: str) -> str:
    escaped = term.replace('"', '\\"')
    return f'"{escaped}"'


def _process_pr(
    *,
    db: Database,
    gh: GitHubClient,
    settings: Settings,
    repo: dict[str, Any],
    pr: dict[str, Any],
    start: float,
    case_count: int,
    repo_case_count: int | None = None,
    prefetched_links: list[tuple[int, str]] | None = None,
) -> tuple[int, int]:
    cfg = settings.config
    include_merged = bool(cfg.get("github", {}).get("include_merged_prs", True))
    include_closed_unmerged = bool(cfg.get("github", {}).get("include_closed_unmerged_prs", False))
    min_words = int(cfg.get("filters", {}).get("min_issue_words", 0))
    english_only = bool(cfg.get("filters", {}).get("english_only", False))
    require_issue_quality = bool(cfg.get("collection", {}).get("require_issue_quality_filter", False))
    excluded_bots = cfg.get("filters", {}).get("exclude_bots", []) or []
    per_page = int(cfg.get("github", {}).get("per_page", 50))

    full_name = repo["full_name"]
    pr_num = pr["number"]
    repo_case_count = int(repo_case_count or 0)
    max_cases_per_repo = settings.limits.max_cases_per_repo
    merged = pr.get("merged_at") is not None or bool(pr.get("merged", False))
    lookback_months = _lookback_months(settings)
    lookback_start = _lookback_start(settings)
    log_exclusions = bool(cfg.get("collection", {}).get("log_excluded_cases", True))
    exclude_non_behaviour = bool(cfg.get("filters", {}).get("exclude_non_behaviour_only", True))

    pr_date_for_lookback = pr.get("merged_at") if bool(cfg.get("collection", {}).get("require_pr_merged_after_lookback", True)) else (pr.get("merged_at") or pr.get("closed_at") or pr.get("updated_at") or pr.get("created_at"))
    if not _within_lookback(pr_date_for_lookback, lookback_months, lookback_start):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "outside_lookback_pr", f"PR merged_at outside {_lookback_description(lookback_months, lookback_start)}; merged_at={pr.get('merged_at')} closed_at={pr.get('closed_at')} updated_at={pr.get('updated_at')} created_at={pr.get('created_at')}")
        return case_count, int(repo_case_count or 0)
    if merged and not include_merged:
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "merged_prs_disabled", "Merged PRs disabled by config")
        return case_count, int(repo_case_count or 0)
    if (not merged) and not include_closed_unmerged:
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "unmerged_pr", "Closed/unmerged PR excluded by config")
        return case_count, int(repo_case_count or 0)
    if is_excluded_bot((pr.get("user") or {}).get("login"), pr.get("title"), (pr.get("head") or {}).get("ref"), excluded_bots):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "bot_maintenance", "Excluded bot PR")
        return case_count, int(repo_case_count or 0)

    try:
        files = enrich_files(list(gh.paginate(f"/repos/{full_name}/pulls/{pr_num}/files", {"per_page": 100})))
    except GitHubAPIError as e:
        # GitHub can fail to generate very large PR diffs/file lists, e.g. HTTP 422
        # {"message":"Server Error: Sorry, this diff is taking too long to generate"}.
        # This is an inaccessible PR artifact, not a reason to abort an overnight run.
        log.warning("Skipping PR %s#%s because changed files are unavailable: %s", full_name, pr_num, e)
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "pr_files_unavailable", str(e))
        return case_count, int(repo_case_count or 0)
    except Exception as e:
        log.warning("Skipping PR %s#%s because changed files could not be fetched: %s", full_name, pr_num, e)
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "pr_files_unavailable", str(e))
        return case_count, int(repo_case_count or 0)


    if bool(
        cfg.get("collection", {}).get(
            "require_javascript_typescript_surface",
            False,
        )
    ) and not has_javascript_typescript_surface(files):
        if log_exclusions:
            db.log_excluded_case(
                full_name,
                None,
                pr_num,
                "no_javascript_typescript_surface",
                (
                    "PR did not change JS/TS source, package/dependency files, "
                    "JS tooling configuration, CI, or relevant scripts"
                ),
                files,
            )
        return case_count, int(repo_case_count or 0)

    behaviour_class = classify_pr_files(files)
    if exclude_non_behaviour and behaviour_class == "non_behaviour_only":
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "non_behaviour_only", "All changed files are clearly prose/assets/legal/release-only", files)
        return case_count, int(repo_case_count or 0)

    if bool(cfg.get("filters", {}).get("exclude_docs_scope_only", cfg.get("filters", {}).get("exclude_docs_only", True))) and is_docs_scope_only(files):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "docs_only_change", "All changed files are confined to documentation scope", files)
        return case_count, int(repo_case_count or 0)

    max_changed_files = int(cfg.get("collection", {}).get("max_changed_files_for_evidence", 75) or 0)
    if max_changed_files and len(files) > max_changed_files:
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "pr_scope_too_large_for_evidence", f"changed files {len(files)} > max_changed_files_for_evidence {max_changed_files}; broad PRs weaken issue→PR causal evidence", files[:50])
        return case_count, int(repo_case_count or 0)

    require_primary_worker = bool(cfg.get("collection", {}).get("require_primary_worker", True))
    if require_primary_worker and not has_primary_applicable_downstream_worker(files):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "no_primary_worker_applicable", str(route_reasons(files)), files)
        return case_count, int(repo_case_count or 0)
    if (not require_primary_worker) and not has_any_applicable_downstream_worker(files):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "not_tool_applicable", str(route_reasons(files)), files)
        return case_count, int(repo_case_count or 0)

    require_high_yield = bool(cfg.get("collection", {}).get("require_high_yield_surface", True))
    if require_high_yield and not has_high_yield_downstream_surface(files):
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "low_yield_downstream_surface", "No dependency/CI/security-sensitive source surface; routes=" + str(route_reasons(files)), files)
        return case_count, int(repo_case_count or 0)

    links = list(prefetched_links or [])
    if not links:
        links = find_linked_issue_numbers(pr.get("title"), pr.get("body"), (pr.get("head") or {}).get("ref"), current_repo=full_name)
    # GitHub issue search can match PR comments as well as title/body. If the
    # search result looked issue-linked but the full PR body did not contain the
    # link, inspect a small bounded set of PR issue comments before excluding.
    if not links and bool(cfg.get("collection", {}).get("fetch_pr_comments_for_issue_links", True)):
        try:
            comment_texts = []
            for idx, comment in enumerate(gh.paginate(f"/repos/{full_name}/issues/{pr_num}/comments", {"per_page": 100}, max_pages=1)):
                if idx >= 100:
                    break
                body = (comment.get("body") or "").strip()
                if body:
                    comment_texts.append(body)
            if comment_texts:
                links = find_linked_issue_numbers(*comment_texts, current_repo=full_name)
        except Exception as e:
            log.debug("Could not fetch PR comments for issue-link fallback %s#%s: %s", full_name, pr_num, e)
    if not links and bool(cfg.get("collection", {}).get("fetch_commit_messages_for_issue_links", True)):
        commit_text = _safe_commit_messages(gh, full_name, pr_num, True, max_messages=30)
        if commit_text:
            links = find_linked_issue_numbers(commit_text, current_repo=full_name)
    if not links:
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "no_linked_issue", "No linked issue detected in PR title/body/head branch, first PR comments page, or commit messages", files)
        return case_count, int(repo_case_count or 0)

    # Evidence cases need a reasonably direct issue→PR relationship. A PR that
    # closes many issues is often a broad batch/migration PR and is weak causal
    # evidence for any single issue description. Keep this as an explicit,
    # configurable exclusion rather than silently creating duplicate cases.
    unique_links: list[tuple[int, str]] = []
    seen_issue_nums: set[int] = set()
    for issue_num, link_method in links:
        if int(issue_num) not in seen_issue_nums:
            seen_issue_nums.add(int(issue_num))
            unique_links.append((int(issue_num), link_method))
    links = unique_links
    max_linked_issues = int(cfg.get("collection", {}).get("max_linked_issues_per_pr_for_evidence", 1) or 0)
    if max_linked_issues and len(links) > max_linked_issues:
        if log_exclusions:
            db.log_excluded_case(full_name, None, pr_num, "ambiguous_multi_issue_pr", f"PR has {len(links)} same-repo linked issues; max_linked_issues_per_pr_for_evidence={max_linked_issues}; linked={links[:10]}", files[:50])
        return case_count, int(repo_case_count or 0)

    repo_id = db.insert_or_get_repo(repo)
    pr_id = db.upsert_pr(repo_id, pr)
    db.replace_pr_files(pr_id, files)

    for issue_num, link_method in links:
        if max_cases_per_repo and repo_case_count >= max_cases_per_repo:
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "over_repo_cap", f"Repo cap reached: {max_cases_per_repo}", files if 'files' in locals() else None)
            break
        if settings.limits.max_cases and case_count >= settings.limits.max_cases:
            break
        if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
            break
        try:
            issue = gh.get(f"/repos/{full_name}/issues/{issue_num}")
        except Exception as e:
            log.warning("Could not fetch issue %s#%s: %s", full_name, issue_num, e)
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "inaccessible_issue", str(e), files)
            continue
        issue_date_for_lookback = issue.get("created_at") if bool(cfg.get("collection", {}).get("require_issue_created_after_lookback", True)) else (issue.get("closed_at") or issue.get("updated_at") or issue.get("created_at"))
        if not _within_lookback(issue_date_for_lookback, lookback_months, lookback_start):
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "outside_lookback_issue", f"Issue created_at outside {_lookback_description(lookback_months, lookback_start)}; issue_created_at={issue.get('created_at')} issue_updated_at={issue.get('updated_at')} issue_closed_at={issue.get('closed_at')}", files)
            continue
        if "pull_request" in issue:
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "linked_item_is_pr", "Linked item is a pull request, not an issue", files)
            continue
        min_body_chars = _min_issue_body_chars(settings)
        body_chars = _issue_body_char_count(issue)
        if min_body_chars and body_chars < min_body_chars:
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "issue_body_too_short", f"issue body {body_chars} chars < required {min_body_chars}", files)
            continue
        issue_meta = {"word_count": 0, "is_english": True}
        if require_issue_quality:
            ok, issue_meta = passes_issue_filters(issue, min_words, english_only)
            if not ok:
                if log_exclusions:
                    db.log_excluded_case(full_name, issue_num, pr_num, "issue_filter", str(issue_meta), files)
                continue
        else:
            ok, issue_meta = passes_issue_filters(issue, 0, False)

        commit_messages = _safe_commit_messages(
            gh,
            full_name,
            pr_num,
            bool(cfg.get("collection", {}).get("fetch_commit_messages_for_ai", True)),
        )
        ai_cohort, markers = detect_ai_markers(
            {
                "issue_title": issue.get("title"),
                "issue_body": issue.get("body"),
                "pr_title": pr.get("title"),
                "pr_body": pr.get("body"),
                "pr_branch": (pr.get("head") or {}).get("ref"),
                "pr_author": (pr.get("user") or {}).get("login"),
                "commit_messages": commit_messages,
            },
            cfg,
        )
        if cfg.get("collection", {}).get("ai_only", False) and ai_cohort == "AI-unknown":
            if log_exclusions:
                db.log_excluded_case(full_name, issue_num, pr_num, "ai_marker_required", "SCOPE=ai requires case-level marker", files)
            continue

        issue_id = db.upsert_issue(repo_id, issue, issue_meta["word_count"], issue_meta["is_english"])
        db.link_issue_pr(issue_id, pr_id, link_method)

        features = extract_upstream_features(issue.get("title"), issue.get("body"))
        features["has_ai_marker"] = ai_cohort != "AI-unknown"
        _store_upstream_features(db, issue_id, features)

        auto_tags = [ai_cohort]
        case_id = db.create_or_get_case(repo_id, issue_id, pr_id, ai_cohort, auto_tags)
        for m in markers:
            db.execute(
                "INSERT INTO ai_markers(case_id, issue_id, pr_id, marker_text, marker_location, confidence, matched_tool) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (case_id, issue_id, pr_id, m.marker_text, m.marker_location, m.confidence, m.matched_tool),
            )
        case_count += 1
        repo_case_count += 1
        log.info("Collected case %s: %s issue #%s PR #%s", case_id, full_name, issue_num, pr_num)
    return case_count, int(repo_case_count or 0)



def _github_search_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )


def _parse_agentic_lookback(value: str) -> datetime:
    parsed = datetime.fromisoformat(
        str(value).strip().replace("Z", "+00:00")
    )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return (
        parsed.astimezone(timezone.utc)
        .replace(microsecond=0)
    )


def _bounded_merged_query(
    base_query: str,
    window_start: datetime,
    window_end: datetime,
) -> str:
    """Replace the open merged-date qualifier with an inclusive window."""
    without_merged = re.sub(
        r"(?<!\S)merged:[^\s]+",
        "",
        str(base_query),
        flags=re.IGNORECASE,
    )

    normalized = " ".join(without_merged.split())

    return (
        "%s merged:%s..%s"
        % (
            normalized,
            _github_search_timestamp(window_start),
            _github_search_timestamp(window_end),
        )
    )


def _split_agentic_window(
    window_start: datetime,
    window_end: datetime,
) -> tuple[
    tuple[datetime, datetime],
    tuple[datetime, datetime],
] | None:
    """Split an inclusive UTC window without losing or duplicating seconds."""
    seconds = int(
        (window_end - window_start).total_seconds()
    )

    if seconds <= 0:
        return None

    midpoint = window_start + timedelta(
        seconds=seconds // 2
    )

    right_start = midpoint + timedelta(seconds=1)

    if right_start > window_end:
        return None

    return (
        (window_start, midpoint),
        (right_start, window_end),
    )


def _iter_adaptive_agentic_search(
    gh: GitHubClient,
    base_query: str,
    merged_since: str,
    *,
    enabled: bool,
    legacy_per_page: int,
    legacy_max_pages: int,
    search_per_page: int,
    split_threshold: int,
    max_depth: int,
    end_at: datetime | None = None,
    stats: dict[str, int] | None = None,
):
    """Yield all PR-search results through recursively bounded date windows.

    A count probe is issued for each window. Windows above the safety
    threshold, or marked incomplete by GitHub, are divided until each
    retrievable window is safely below GitHub's 1,000-result boundary.
    """
    # Runtime callers normally leave end_at unset. Resolve it before the pre-split condition.
    if end_at is None:
        from datetime import datetime as _agentic_datetime
        from datetime import timezone as _agentic_timezone
        end_at = _agentic_datetime.now(
            _agentic_timezone.utc
        )

    # BEGIN AGENTIC INITIAL WINDOW PRE-SPLIT
    # Do not ask GitHub Search to calculate total_count for a
    # multi-month query. Such broad count probes are expensive
    # even with per_page=1 and can trigger secondary limits.
    if enabled and end_at is not None:
        from datetime import timedelta as _agentic_timedelta
    
        _agentic_initial_start = (
            _parse_agentic_lookback(
                merged_since
            )
        )
    
        _agentic_max_initial_window = (
            _agentic_timedelta(days=7)
        )
    
        if (
            end_at - _agentic_initial_start
            > _agentic_max_initial_window
        ):
            _agentic_chunk_start = (
                _agentic_initial_start
            )
    
            while _agentic_chunk_start < end_at:
                _agentic_chunk_end = min(
                    _agentic_chunk_start
                    + _agentic_max_initial_window,
                    end_at,
                )
    
                yield from (
                    _iter_adaptive_agentic_search(
            gh,
            base_query,
            _github_search_timestamp(_agentic_chunk_start),
            enabled=enabled,
            legacy_per_page=legacy_per_page,
            legacy_max_pages=legacy_max_pages,
            search_per_page=search_per_page,
            split_threshold=split_threshold,
            max_depth=max_depth,
            end_at=_agentic_chunk_end,
            stats=stats,
                    )
                )
    
                _agentic_chunk_start = (
                    _agentic_chunk_end
                )
    
            return
    # END AGENTIC INITIAL WINDOW PRE-SPLIT
    if stats is None:
        stats = {}

    stats.update({
        "search_window_count": 0,
        "split_window_count": 0,
        "probe_count": 0,
        "reported_total_count": 0,
    })

    if not enabled:
        yield from gh.search_issues(
            base_query,
            per_page=legacy_per_page,
            max_pages=legacy_max_pages,
        )
        return

    safe_per_page = max(
        1,
        min(int(search_per_page or 100), 100),
    )

    safe_threshold = max(
        1,
        min(int(split_threshold or 900), 999),
    )

    safe_max_depth = max(
        1,
        int(max_depth or 40),
    )

    first_start = _parse_agentic_lookback(
        merged_since
    )

    final_end = (
        end_at
        or datetime.now(timezone.utc)
    )

    final_end = (
        final_end.astimezone(timezone.utc)
        .replace(microsecond=0)
    )

    if final_end < first_start:
        return

    stack: list[
        tuple[datetime, datetime, int]
    ] = [
        (
            first_start,
            final_end,
            0,
        )
    ]

    while stack:
        window_start, window_end, depth = stack.pop()

        window_query = _bounded_merged_query(
            base_query,
            window_start,
            window_end,
        )

        # Use the first response as both the count probe and page 1.
        # The date range is already capped at seven days, so requesting the
        # first full page avoids a second search request for every window.
        probe = gh.search_issues_page(
            window_query,
            per_page=safe_per_page,
            page=1,
        )

        stats["probe_count"] += 1

        total_count = int(
            probe.get("total_count")
            or 0
        )

        incomplete = bool(
            probe.get("incomplete_results")
            or False
        )

        must_split = (
            incomplete
            or total_count > safe_threshold
        )

        if must_split:
            if depth >= safe_max_depth:
                raise RuntimeError(
                    "Adaptive GitHub search exceeded "
                    "max split depth for %s; "
                    "total_count=%s incomplete=%s"
                    % (
                        window_query,
                        total_count,
                        incomplete,
                    )
                )

            divided = _split_agentic_window(
                window_start,
                window_end,
            )

            if divided is None:
                raise RuntimeError(
                    "A one-second GitHub search window "
                    "still exceeds the safe result limit: "
                    "%s total_count=%s incomplete=%s"
                    % (
                        window_query,
                        total_count,
                        incomplete,
                    )
                )

            left_window, right_window = divided

            stats["split_window_count"] += 1

            # Stack is LIFO. Push right first so collection
            # proceeds chronologically from the oldest window.
            stack.append((
                right_window[0],
                right_window[1],
                depth + 1,
            ))

            stack.append((
                left_window[0],
                left_window[1],
                depth + 1,
            ))

            continue

        stats["search_window_count"] += 1
        stats["reported_total_count"] += total_count

        if total_count <= 0:
            continue

        first_items = list(
            probe.get("items")
            or []
        )

        for item in first_items:
            yield item

        page_count = max(
            1,
            int(
                math.ceil(
                    total_count / safe_per_page
                )
            ),
        )

        if page_count > 1:
            yield from gh.search_issues(
                window_query,
                per_page=safe_per_page,
                max_pages=page_count - 1,
                start_page=2,
            )

def _collect_ai_search(
    db: Database,
    gh: GitHubClient,
    settings: Settings,
    start: float,
) -> int:
    """Discover PRs through exact, study-backed agentic GitHub indicators.

    Candidate discovery happens directly through head, author, or PR-body
    qualifiers. Generic AI names, reviewer bots, repository-level AI files,
    and commit-only provenance are intentionally excluded.
    """

    cfg = settings.config
    github_cfg = cfg.get("github", {}) or {}
    collection_cfg = cfg.get("collection", {}) or {}
    ai_search = collection_cfg.get("ai_search", {}) or {}

    languages = _github_languages(settings)
    min_stars = int(github_cfg.get("min_stars", 100) or 100)
    merged_since = str(
        collection_cfg.get("lookback_start", "2025-11-01")
        or "2025-11-01"
    )
    maintenance_authors = _bot_author_terms(settings)

    jobs = build_agentic_query_jobs(
        languages=languages,
        min_stars=min_stars,
        merged_since=merged_since,
        maintenance_authors=maintenance_authors,
    )

    max_queries = int(ai_search.get("max_marker_queries", 0) or 0)
    if max_queries > 0:
        jobs = jobs[:max_queries]

    per_page = int(ai_search.get("per_page", 100) or 100)
    max_pages = int(ai_search.get("max_pages_per_query", 10) or 10)
    pause_seconds = float(ai_search.get("pause_seconds", 0) or 0)

    adaptive_date_partitioning = bool(
        ai_search.get(
            "adaptive_date_partitioning",
            True,
        )
    )

    adaptive_split_threshold = int(
        ai_search.get(
            "adaptive_split_threshold",
            900,
        )
        or 900
    )

    adaptive_search_per_page = int(
        ai_search.get(
            "adaptive_search_per_page",
            100,
        )
        or 100
    )

    adaptive_max_depth = int(
        ai_search.get(
            "adaptive_max_depth",
            40,
        )
        or 40
    )

    repository_eligibility_enabled = bool(
        collection_cfg.get(
            "repository_eligibility_enabled",
            True,
        )
    )

    min_js_ts_share = float(
        collection_cfg.get(
            "min_js_ts_share",
            0.50,
        )
        or 0.50
    )

    force_repo_eligibility_refresh = bool(
        collection_cfg.get(
            "force_repo_eligibility_refresh",
            False,
        )
    )

    use_graphql = bool(collection_cfg.get("use_graphql_hydration", True))

    seen_prs: set[tuple[str, int]] = set()
    repo_cache: dict[str, dict[str, Any]] = {}
    repo_count = 0
    case_count = 0

    log.info(
        "Starting exact agentic discovery. languages=%s indicators=%s "
        "queries=%s merged_since=%s min_stars=%s",
        languages,
        6,
        len(jobs),
        merged_since,
        min_stars,
    )

    stop_for_rate_limit = False

    for job_index, job in enumerate(jobs):
        if _limit_reached(start, settings, repo_count, case_count):
            break

        query = job.query
        stream_key = (
            f"agentic:{job.indicator.key}:"
            f"{job.language.lower()}"
        )
        term = job.indicator.marker_text

        db.execute(
            """
            INSERT INTO retrieval_queries(
                stream_key,
                term,
                final_query,
                status,
                last_run_at,
                next_page,
                exhausted
            )
            VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, 1, 0)
            ON CONFLICT(final_query) DO UPDATE SET
                status='running',
                last_error=NULL,
                last_run_at=CURRENT_TIMESTAMP
            """,
            (stream_key, term, query),
        )

        raw_count = 0
        unique_count = 0
        duplicate_count = 0
        repo_filter_count = 0
        processed_count = 0
        candidate_count = 0
        excluded_start = int(
            (
                db.one("SELECT COUNT(*) AS n FROM excluded_cases")
                or {"n": 0}
            ).get("n")
            or 0
        )

        log.info(
            "Agentic query %s/%s [%s]: %s",
            job_index + 1,
            len(jobs),
            stream_key,
            query,
        )

        if pause_seconds > 0 and job_index > 0:
            time.sleep(pause_seconds)

        adaptive_stats = {
            "search_window_count": 0,
            "split_window_count": 0,
            "probe_count": 0,
            "reported_total_count": 0,
        }

        try:
            items = _iter_adaptive_agentic_search(
                gh,
                query,
                merged_since,
                enabled=adaptive_date_partitioning,
                legacy_per_page=per_page,
                legacy_max_pages=max_pages,
                search_per_page=adaptive_search_per_page,
                split_threshold=adaptive_split_threshold,
                max_depth=adaptive_max_depth,
                stats=adaptive_stats,
            )

            for item in items:
                raw_count += 1
                if _limit_reached(
                    start,
                    settings,
                    repo_count,
                    case_count,
                ):
                    break

                repository_url = str(
                    item.get("repository_url") or ""
                )
                pr_num = int(item.get("number") or 0)

                if not repository_url or pr_num <= 0:
                    continue

                full_name = _repo_full_name_from_url(repository_url)
                key = (full_name.lower(), pr_num)
                unique_count += 1

                if key in seen_prs:
                    duplicate_count += 1
                    for case_id in _case_ids_for_pr(
                        db,
                        full_name,
                        pr_num,
                    ):
                        _record_case_retrieval(
                            db,
                            case_id,
                            stream_key,
                            term,
                            query,
                        )
                    continue

                repo = repo_cache.get(full_name)
                if repo is None:
                    repo = gh.get(f"/repos/{full_name}")
                    repo_cache[full_name] = repo
                    repo_count += 1

                repo_ok, repo_reason = _repo_passes_universe(
                    repo,
                    settings,
                )
                if not repo_ok:
                    repo_filter_count += 1
                    db.log_excluded_case(
                        full_name,
                        None,
                        pr_num,
                        "repo_filter",
                        repo_reason,
                    )
                    continue

                if repository_eligibility_enabled:
                    eligibility = evaluate_repo_eligibility(
                        db,
                        gh,
                        full_name,
                        repo_metadata=repo,
                        min_stars=min_stars,
                        min_js_ts_share=min_js_ts_share,
                        force_refresh=force_repo_eligibility_refresh,
                    )

                    repo = eligibility["repo"]
                    repo_cache[full_name] = repo

                    if not eligibility["eligible"]:
                        repo_filter_count += 1
                        processed_count += 1
                        seen_prs.add(key)

                        details = (
                            "reason=%s; "
                            "stars=%s; "
                            "javascript_bytes=%s; "
                            "typescript_bytes=%s; "
                            "js_ts_bytes=%s; "
                            "total_language_bytes=%s; "
                            "js_ts_share=%.4f; "
                            "required_share=%.4f"
                            % (
                                eligibility["reason"],
                                eligibility["stars"],
                                eligibility["javascript_bytes"],
                                eligibility["typescript_bytes"],
                                eligibility["js_ts_bytes"],
                                eligibility["total_language_bytes"],
                                eligibility["js_ts_share"],
                                min_js_ts_share,
                            )
                        )

                        db.log_excluded_case(
                            full_name,
                            None,
                            pr_num,
                            "repo_js_ts_share_filter",
                            details,
                        )

                        _pipeline_event(
                            db,
                            "repo_js_ts_share_filter",
                            "%s#%s %s"
                            % (
                                full_name,
                                pr_num,
                                details,
                            ),
                        )

                        continue

                try:
                    pr = gh.get(
                        f"/repos/{full_name}/pulls/{pr_num}"
                    )
                except Exception as exc:
                    processed_count += 1
                    db.log_excluded_case(
                        full_name,
                        None,
                        pr_num,
                        "pr_hydration_failed",
                        str(exc),
                    )
                    continue

                marker_ok, marker_reason = validate_pr_for_job(
                    pr,
                    job,
                )
                if not marker_ok:
                    processed_count += 1
                    db.log_excluded_case(
                        full_name,
                        None,
                        pr_num,
                        "agentic_indicator_validation_failed",
                        (
                            f"indicator={job.indicator.key}; "
                            f"language={job.language}; "
                            f"{marker_reason}"
                        ),
                    )
                    continue

                seen_prs.add(key)
                processed_count += 1

                hydration = _graphql_hydrate_pr(
                    gh,
                    full_name,
                    pr_num,
                    enabled=use_graphql,
                )
                prefetched_links = _same_repo_graphql_issue_links(
                    hydration,
                    full_name,
                )

                old_case_count = case_count

                try:
                    case_count, _ = _process_pr(
                        db=db,
                        gh=gh,
                        settings=settings,
                        repo=repo,
                        pr=pr,
                        start=start,
                        case_count=case_count,
                        repo_case_count=0,
                        prefetched_links=prefetched_links,
                    )
                except Exception as exc:
                    log.warning(
                        "Skipping agentic PR %s#%s after "
                        "processing failure: %s",
                        full_name,
                        pr_num,
                        exc,
                    )
                    db.log_excluded_case(
                        full_name,
                        None,
                        pr_num,
                        "processing_error",
                        str(exc),
                    )
                    continue

                created = max(0, case_count - old_case_count)
                candidate_count += created

                for case_id in _case_ids_for_pr(
                    db,
                    full_name,
                    pr_num,
                ):
                    _record_case_retrieval(
                        db,
                        case_id,
                        stream_key,
                        term,
                        query,
                    )

        except GitHubSecondaryRateLimit as exc:
            stop_for_rate_limit = True
            db.execute(
                """
                UPDATE retrieval_queries
                SET status='rate_limited',
                    last_error=?,
                    last_run_at=CURRENT_TIMESTAMP
                WHERE final_query=?
                """,
                (str(exc)[:1000], query),
            )
            log.warning(
                "Secondary rate limit during agentic query; "
                "ending this pass safely: %s",
                exc,
            )

        except Exception as exc:
            db.execute(
                """
                UPDATE retrieval_queries
                SET status='error',
                    last_error=?,
                    last_run_at=CURRENT_TIMESTAMP
                WHERE final_query=?
                """,
                (str(exc)[:1000], query),
            )
            log.warning(
                "Agentic query failed %r: %s",
                query,
                exc,
            )

        finally:
            excluded_end = int(
                (
                    db.one(
                        "SELECT COUNT(*) AS n FROM excluded_cases"
                    )
                    or {"n": excluded_start}
                ).get("n")
                or 0
            )
            excluded_count = max(
                0,
                excluded_end - excluded_start,
            )

            db.execute(
                """
                UPDATE retrieval_queries
                SET raw_count=COALESCE(raw_count, 0)+?,
                    unique_count=COALESCE(unique_count, 0)+?,
                    eligible_count=COALESCE(eligible_count, 0)+?,
                    candidate_count=COALESCE(candidate_count, 0)+?,
                    duplicate_count=COALESCE(duplicate_count, 0)+?,
                    repo_filter_count=COALESCE(repo_filter_count, 0)+?,
                    processed_count=COALESCE(processed_count, 0)+?,
                    excluded_count=COALESCE(excluded_count, 0)+?,
                    search_window_count=?,
                    split_window_count=?,
                    probe_count=?,
                    reported_total_count=?,
                    status=CASE
                        WHEN status='running' THEN 'ok'
                        ELSE status
                    END,
                    exhausted=CASE
                        WHEN status='rate_limited' THEN 0
                        ELSE 1
                    END,
                    last_run_at=CURRENT_TIMESTAMP
                WHERE final_query=?
                """,
                (
                    raw_count,
                    unique_count,
                    processed_count,
                    candidate_count,
                    duplicate_count,
                    repo_filter_count,
                    processed_count,
                    excluded_count,
                    adaptive_stats["search_window_count"],
                    adaptive_stats["split_window_count"],
                    adaptive_stats["probe_count"],
                    adaptive_stats["reported_total_count"],
                    query,
                ),
            )

        if stop_for_rate_limit:
            break

    log.info(
        "Exact agentic collection complete. "
        "repos=%s unique_prs=%s cases=%s",
        repo_count,
        len(seen_prs),
        case_count,
    )
    return case_count






def _collect_targeted_stream_search(db: Database, gh: GitHubClient, settings: Settings, start: float, initial_case_count: int = 0) -> int:
    """Collect using the UI-visible base+stream PR search strategy.

    This is the default for live/mine. It avoids broad repo-walking and instead
    asks GitHub for merged Python PRs from popular non-archived repos that match
    one stream term, then validates same-repo issue linkage before scanning.
    """
    cfg = settings.config
    case_count = initial_case_count
    min_stars = int(cfg.get("github", {}).get("min_stars", 200))
    wanted_language = str(cfg.get("github", {}).get("language", "Python")).lower()
    strict_primary_language = bool(cfg.get("github", {}).get("strict_primary_language", False))
    per_page = int(cfg.get("collection", {}).get("targeted_per_page", cfg.get("collection", {}).get("ai_search", {}).get("per_page", 25)) or 25)
    raw_pages = cfg.get("collection", {}).get("targeted_max_pages", cfg.get("collection", {}).get("ai_search", {}).get("max_pages_per_query", 1))
    try:
        pages_per_pass = max(1, int(raw_pages or 1))
    except (TypeError, ValueError):
        pages_per_pass = 1
    raw_total_pages = cfg.get("collection", {}).get("targeted_max_pages_total", 3)
    try:
        max_pages_total = max(1, int(raw_total_pages or 3))
    except (TypeError, ValueError):
        max_pages_total = 3
    max_terms = int(cfg.get("collection", {}).get("targeted_max_terms", 0) or 0)
    pause_seconds = int(cfg.get("collection", {}).get("targeted_pause_seconds", cfg.get("collection", {}).get("ai_search", {}).get("pause_seconds", 25)) or 25)
    max_processed_prs_per_repo = int(cfg.get("collection", {}).get("max_processed_prs_per_repo", 10) or 10)
    max_raw_hits_per_repo_per_pass = int(cfg.get("collection", {}).get("max_raw_hits_per_repo_per_pass", 5) or 5)
    max_prs_per_repo_per_query = int(cfg.get("collection", {}).get("max_prs_per_repo_per_query", 1) or 0)
    max_new_prs_per_repo_per_run = int(cfg.get("collection", {}).get("max_new_prs_per_repo_per_run", 2) or 0)

    query_jobs: list[tuple[str, str, str]] = _targeted_query_jobs(settings)
    if max_terms > 0:
        query_jobs = query_jobs[:max_terms]

    log.info("Starting targeted stream collection with base query: %s | query_jobs=%s | pages_per_pass=%s | max_pages_total=%s | per_page=%s", _targeted_base_query(settings), len(query_jobs), pages_per_pass, max_pages_total, per_page)
    seen_prs: set[tuple[str, int]] = set()
    seen_repos: dict[str, dict[str, Any]] = {}
    repo_count = 0
    raw_total = 0
    repo_raw_hits_this_pass: dict[str, int] = {}
    repo_new_prs_this_run: dict[str, int] = {}

    for idx, (stream_key, term, q) in enumerate(query_jobs, start=1):
        if _limit_reached(start, settings, repo_count, case_count):
            break
        log.info("Targeted stream query %s/%s [%s]: %s", idx, len(query_jobs), stream_key, q)
        db.execute(
            """
            INSERT INTO retrieval_queries(stream_key, term, final_query, status, last_run_at, next_page, exhausted)
            VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, 1, 0)
            ON CONFLICT(final_query) DO UPDATE SET status='running', last_run_at=CURRENT_TIMESTAMP
            """,
            (stream_key, term, q),
        )
        qstate = db.one("SELECT next_page, exhausted FROM retrieval_queries WHERE final_query=?", (q,)) or {}
        if int(qstate.get("exhausted") or 0):
            log.info("Targeted stream query exhausted; skipping this pass: %s", q)
            db.execute("UPDATE retrieval_queries SET status='exhausted', last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (q,))
            continue
        start_page = max(1, int(qstate.get("next_page") or 1))
        if start_page > max_pages_total:
            log.info("Targeted stream query reached configured page cap; marking exhausted: %s", q)
            db.execute("UPDATE retrieval_queries SET exhausted=1, status='exhausted', last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (q,))
            continue
        raw_count = 0
        unique_count = 0
        eligible_count = 0
        candidate_count_delta = 0
        duplicate_count = 0
        repo_filter_count = 0
        processed_count = 0
        excluded_start_row = db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": 0}
        excluded_start = int(excluded_start_row.get("n") or 0)
        query_completed = False
        unique_prs_this_query: set[tuple[str, int]] = set()
        repo_hits_this_query: dict[str, int] = {}
        try:
            items = list(gh.search_issues(q, per_page=per_page, max_pages=pages_per_pass, start_page=start_page))
            query_completed = True
            raw_count = len(items)
            raw_total += raw_count
            for item in items:
                if _limit_reached(start, settings, repo_count, case_count):
                    break
                pr_info = item.get("pull_request") or {}
                pr_api_url = pr_info.get("url")
                repo_url = item.get("repository_url")
                if not pr_api_url or not repo_url:
                    processed_count += 1
                    _pipeline_event(db, "malformed_search_hit", f"query={q} number={item.get('number')}")
                    continue
                full_name = _repo_full_name_from_url(repo_url)
                pr_num = int(item.get("number") or 0)
                if pr_num <= 0:
                    continue
                key = (full_name, pr_num)
                unique_prs_this_query.add(key)
                repo_hits_this_query[full_name] = repo_hits_this_query.get(full_name, 0) + 1
                if max_prs_per_repo_per_query and repo_hits_this_query[full_name] > max_prs_per_repo_per_query:
                    repo_filter_count += 1
                    processed_count += 1
                    _pipeline_event(db, "repo_query_repeat", f"{full_name}#{pr_num} query={q} cap={max_prs_per_repo_per_query}")
                    continue
                repo_raw_hits_this_pass[full_name] = repo_raw_hits_this_pass.get(full_name, 0) + 1
                if max_raw_hits_per_repo_per_pass and repo_raw_hits_this_pass[full_name] > max_raw_hits_per_repo_per_pass:
                    repo_filter_count += 1
                    processed_count += 1
                    db.log_excluded_case(full_name, None, pr_num, "repo_query_cap", f"Per-pass raw-hit cap reached for repo: {max_raw_hits_per_repo_per_pass}")
                    _pipeline_event(db, "repo_query_cap", f"{full_name}#{pr_num} query={q}")
                    continue

                if max_processed_prs_per_repo and _repo_visible_outcome_count(db, full_name) >= max_processed_prs_per_repo:
                    repo_filter_count += 1
                    processed_count += 1
                    db.log_excluded_case(full_name, None, pr_num, "repo_cap_reached", f"Repo already has {max_processed_prs_per_repo}+ visible processed outcomes")
                    _pipeline_event(db, "repo_cap_reached", f"{full_name}#{pr_num} cap={max_processed_prs_per_repo}")
                    continue

                duplicate = key in seen_prs
                seen_prs.add(key)

                # Account for outcomes produced by earlier runs before doing
                # expensive API calls. Without this, a restarted live run can
                # show large raw/unique counts but almost no processed/excluded
                # movement, because old PR outcomes are invisible to the current
                # in-memory seen_prs set.
                known = _known_pr_outcomes(db, full_name, pr_num)
                if known["cases"] or known["exclusions"]:
                    duplicate_count += 1
                    processed_count += 1
                    if known["cases"]:
                        eligible_count += known["cases"]
                        candidate_count_delta += known["cases"]
                        for case_id in _case_ids_for_pr(db, full_name, pr_num):
                            _record_case_retrieval(db, case_id, stream_key, term, q)
                    _pipeline_event(db, "duplicate_known_outcome", f"{full_name}#{pr_num} stream={stream_key} term={term} cases={known['cases']} exclusions={known['exclusions']}")
                    continue

                if max_new_prs_per_repo_per_run and repo_new_prs_this_run.get(full_name, 0) >= max_new_prs_per_repo_per_run:
                    repo_filter_count += 1
                    processed_count += 1
                    _pipeline_event(db, "repo_run_budget", f"{full_name}#{pr_num} query={q} cap={max_new_prs_per_repo_per_run}")
                    continue

                repo = seen_repos.get(full_name)
                if repo is None:
                    repo = gh.get(f"/repos/{full_name}")
                    seen_repos[full_name] = repo
                    repo_count += 1
                if int(repo.get("stargazers_count") or 0) < min_stars:
                    repo_filter_count += 1
                    processed_count += 1
                    db.log_excluded_case(full_name, None, pr_num, "repo_filter", f"Repo has fewer than {min_stars} stars; stars={repo.get('stargazers_count')}")
                    _pipeline_event(db, "repo_filter", f"{full_name}#{pr_num} stars={repo.get('stargazers_count')}")
                    continue
                if strict_primary_language and wanted_language and str(repo.get("language") or "").lower() != wanted_language:
                    repo_filter_count += 1
                    processed_count += 1
                    db.log_excluded_case(full_name, None, pr_num, "repo_filter", f"Repo primary language is not {wanted_language}; language={repo.get('language')}")
                    _pipeline_event(db, "repo_filter", f"{full_name}#{pr_num} language={repo.get('language')}")
                    continue
                if (not strict_primary_language) and wanted_language and str(repo.get("language") or "").lower() != wanted_language:
                    _pipeline_event(db, "repo_language_soft_mismatch", f"{full_name}#{pr_num} primary_language={repo.get('language')} search_language={wanted_language}")
                if repo.get("archived"):
                    repo_filter_count += 1
                    processed_count += 1
                    db.log_excluded_case(full_name, None, pr_num, "repo_filter", "Repo is archived")
                    _pipeline_event(db, "repo_filter", f"{full_name}#{pr_num} archived")
                    continue

                # Even if the PR was seen before, record the additional retrieval
                # provenance if the case already exists. Do not process duplicate
                # PRs repeatedly.
                if duplicate:
                    duplicate_count += 1
                    processed_count += 1
                    existing_cases = _case_ids_for_pr(db, full_name, pr_num)
                    if existing_cases:
                        eligible_count += len(existing_cases)
                        candidate_count_delta += len(existing_cases)
                    for case_id in existing_cases:
                        _record_case_retrieval(db, case_id, stream_key, term, q)
                    _pipeline_event(db, "duplicate_search_hit", f"{full_name}#{pr_num} stream={stream_key} term={term} cases={len(existing_cases)}")
                    continue

                old_count = case_count
                repo_new_prs_this_run[full_name] = repo_new_prs_this_run.get(full_name, 0) + 1
                try:
                    pr = gh.get(f"/repos/{full_name}/pulls/{pr_num}")
                    processed_count += 1
                    case_count, _repo_cases = _process_pr(db=db, gh=gh, settings=settings, repo=repo, pr=pr, start=start, case_count=case_count)
                    new_cases = max(0, case_count - old_count)
                    if new_cases > 0:
                        eligible_count += new_cases
                        candidate_count_delta += new_cases
                    for case_id in _case_ids_for_pr(db, full_name, pr_num):
                        _record_case_retrieval(db, case_id, stream_key, term, q)
                except Exception as e:
                    processed_count += 1
                    log.warning("Skipping targeted PR %s#%s after processing failure: %s", full_name, pr_num, e)
                    try:
                        db.log_excluded_case(full_name, None, pr_num, "processing_error", str(e))
                    except Exception:
                        log.exception("Could not log processing_error for targeted PR %s#%s", full_name, pr_num)
                    continue
        except GitHubSecondaryRateLimit as e:
            wait = max(int(getattr(e, "wait_seconds", pause_seconds)), pause_seconds)
            log.warning("Secondary limit during targeted query %r. Sleeping %ss and ending this pass safely: %s", q, wait, e)
            db.execute("UPDATE retrieval_queries SET status='rate_limited', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(e)[:1000], q))
            time.sleep(wait)
            break
        except GitHubAPIError as e:
            if gh.is_search_1000_limit_error(e):
                log.info("Targeted stream query reached GitHub 1000-result window; marking exhausted: %s", q)
                db.execute("UPDATE retrieval_queries SET exhausted=1, status='exhausted', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(e)[:1000], q))
            else:
                log.warning("Targeted stream query failed [%s] %r: %s", stream_key, q, e)
                db.execute("UPDATE retrieval_queries SET status='error', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(e)[:1000], q))
        except Exception as e:
            log.warning("Targeted stream query failed [%s] %r: %s", stream_key, q, e)
            db.execute("UPDATE retrieval_queries SET status='error', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(e)[:1000], q))
        finally:
            if query_completed:
                safe_per_page = max(1, min(int(per_page or 25), 100))
                search_cap_pages = max(1, 1000 // safe_per_page)
                pages_fetched = int(math.ceil(raw_count / safe_per_page)) if raw_count > 0 else 0
                if pages_fetched <= 0:
                    exhausted = 1
                    next_page = start_page
                else:
                    next_page = start_page + pages_fetched
                    exhausted = 1 if (raw_count < safe_per_page * pages_per_pass or next_page > search_cap_pages or next_page > max_pages_total) else 0
                unique_count = len(unique_prs_this_query)
                excluded_end_row = db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": excluded_start}
                excluded_delta = max(0, int(excluded_end_row.get("n") or 0) - excluded_start)
                db.execute(
                    """
                    UPDATE retrieval_queries
                    SET raw_count=COALESCE(raw_count,0)+?,
                        unique_count=COALESCE(unique_count,0)+?,
                        eligible_count=COALESCE(eligible_count,0)+?,
                        candidate_count=COALESCE(candidate_count,0)+?,
                        duplicate_count=COALESCE(duplicate_count,0)+?,
                        repo_filter_count=COALESCE(repo_filter_count,0)+?,
                        processed_count=COALESCE(processed_count,0)+?,
                        excluded_count=COALESCE(excluded_count,0)+?,
                        next_page=?,
                        exhausted=CASE WHEN ?=1 THEN 1 ELSE exhausted END,
                        status=CASE WHEN ?=1 THEN 'exhausted' ELSE 'ok' END,
                        last_error=CASE WHEN ?=1 THEN COALESCE(last_error,'') ELSE '' END,
                        last_run_at=CURRENT_TIMESTAMP
                    WHERE final_query=? AND status NOT IN ('error','rate_limited')
                    """,
                    (raw_count, unique_count, eligible_count, candidate_count_delta, duplicate_count, repo_filter_count, processed_count, excluded_delta, next_page, exhausted, exhausted, exhausted, q),
                )
                _pipeline_event(db, "retrieval_query_accounting", f"query={q} raw={raw_count} unique={unique_count} duplicates={duplicate_count} repo_filter={repo_filter_count} processed={processed_count} excluded_delta={excluded_delta} cases_delta={candidate_count_delta}")
        if pause_seconds > 0:
            time.sleep(min(pause_seconds, 5))
    log.info("Targeted stream collection complete. raw_results=%s unique_prs=%s cases=%s", raw_total, len(seen_prs), case_count)
    return case_count

def _collect_repo_walk(db: Database, gh: GitHubClient, settings: Settings, start: float, initial_case_count: int = 0) -> int:
    cfg = settings.config
    repo_count = 0
    case_count = initial_case_count
    per_page = int(cfg.get("github", {}).get("per_page", 50))
    query = cfg.get("github", {}).get("search_query") or f"language:{cfg.get('github', {}).get('language', 'Python')} stars:>={cfg.get('github', {}).get('min_stars', 100)} archived:false"

    repo_strategy = _sample_strategy(settings, "repo_sample_strategy", "none")
    case_strategy = _sample_strategy(settings, "case_sample_strategy", "none")
    seed = _random_seed(settings)
    max_repos = settings.limits.max_repos
    max_prs = settings.limits.max_prs
    max_cases_per_repo = settings.limits.max_cases_per_repo

    log.info(
        "Starting collection with query: %s | repo_strategy=%s | case_strategy=%s | seed=%s | max_cases_per_repo=%s",
        query,
        repo_strategy,
        case_strategy,
        seed,
        max_cases_per_repo,
    )

    repo_iter: Iterable[dict[str, Any]]
    if repo_strategy == "random" and max_repos:
        pool_limit = max_repos * _pool_multiplier(settings, "repo_sample_pool_multiplier", 4)
        repo_pool: list[dict[str, Any]] = []
        for repo in gh.search_repos(query, per_page=per_page):
            repo_pool.append(repo)
            if len(repo_pool) >= pool_limit:
                break
            if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
                break
        repo_iter = _stable_shuffle(repo_pool, seed, "repo")[:max_repos]
        log.info("Randomized repo sample: selected %s from pool of %s", len(list(repo_iter)) if isinstance(repo_iter, list) else max_repos, len(repo_pool))
    else:
        repo_iter = gh.search_repos(query, per_page=per_page)

    for repo in repo_iter:
        if _limit_reached(start, settings, repo_count, case_count):
            break
        repo_count += 1
        repo_case_count = 0
        full_name = repo["full_name"]
        db.insert_or_get_repo(repo)
        log.info("Repo %s", full_name)

        pr_params = {"state": "closed", "sort": "updated", "direction": "desc", "per_page": per_page}
        try:
            if case_strategy == "random" and max_prs:
                pr_pool_limit = max_prs * _pool_multiplier(settings, "case_sample_pool_multiplier", 4)
                pr_pool: list[dict[str, Any]] = []
                for pr_stub in gh.paginate(f"/repos/{full_name}/pulls", pr_params):
                    pr_pool.append(pr_stub)
                    if len(pr_pool) >= pr_pool_limit:
                        break
                    if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
                        break
                pr_candidates = _stable_shuffle(pr_pool, seed, f"pr:{full_name}")[:max_prs]
                log.info("Randomized PR sample for %s: selected %s from pool of %s", full_name, len(pr_candidates), len(pr_pool))
            else:
                pr_limit = max_prs or int(cfg.get("collection", {}).get("max_prs_without_random", 200))
                pr_candidates = []
                for pr_stub in gh.paginate(f"/repos/{full_name}/pulls", pr_params):
                    pr_candidates.append(pr_stub)
                    if pr_limit and len(pr_candidates) >= pr_limit:
                        break
                    if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
                        break
        except Exception as e:
            log.warning("Skipping repo %s because PR list could not be fetched: %s", full_name, e)
            try:
                db.log_excluded_case(full_name, None, None, "repo_pr_list_unavailable", str(e))
            except Exception:
                log.exception("Could not log repo_pr_list_unavailable for %s", full_name)
            continue

        pr_seen = 0
        for pr_stub in pr_candidates:
            if max_prs and pr_seen >= max_prs:
                break
            if max_cases_per_repo and repo_case_count >= max_cases_per_repo:
                log.info("Repo case cap reached for %s: %s", full_name, repo_case_count)
                break
            if settings.limits.max_cases and case_count >= settings.limits.max_cases:
                break
            if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
                break
            pr_seen += 1
            try:
                pr = gh.get(f"/repos/{full_name}/pulls/{pr_stub['number']}")
            except Exception as e:
                # Search/list endpoints can occasionally surface references to PRs that are no
                # longer accessible, moved, deleted, or hidden by permissions. Do not crash an
                # hours-long collection run because of one 404/permission edge case.
                log.warning("Could not fetch PR %s#%s: %s", full_name, pr_stub.get("number"), e)
                continue
            try:
                case_count, repo_case_count = _process_pr(
                    db=db,
                    gh=gh,
                    settings=settings,
                    repo=repo,
                    pr=pr,
                    start=start,
                    case_count=case_count,
                    repo_case_count=repo_case_count,
                )
            except Exception as e:
                # A single malformed/unavailable PR must not abort a long collection run.
                log.warning("Skipping PR %s#%s after processing failure: %s", full_name, pr_stub.get("number"), e)
                try:
                    db.log_excluded_case(full_name, None, pr_stub.get("number"), "processing_error", str(e))
                except Exception:
                    log.exception("Could not log processing_error for %s#%s", full_name, pr_stub.get("number"))
                continue
    log.info("Repo-walk collection complete. repos=%s cases=%s", repo_count, case_count)
    return case_count



def _bot_author_terms(settings: Settings) -> list[str]:
    raw = settings.config.get("filters", {}).get("exclude_bots", []) or []
    out: list[str] = []
    for term in raw:
        t = str(term).strip()
        if not t:
            continue
        if t.endswith("[bot]"):
            out.append(t)
        else:
            out.append(f"{t}[bot]" if t in {"dependabot", "renovate", "github-actions", "pre-commit-ci", "mergify", "pyup"} else t)
    # Ensure the supervisor-required maintenance bots are excluded even when a
    # custom config omits them.
    for required in ("dependabot[bot]", "renovate[bot]", "github-actions[bot]", "pre-commit-ci[bot]", "mergify[bot]"):
        if required not in out:
            out.append(required)
    return out




def _github_languages(settings: Settings) -> list[str]:
    github_cfg = settings.config.get("github", {}) or {}
    raw = github_cfg.get("languages") or settings.config.get("collection", {}).get("github_languages")
    if isinstance(raw, str):
        langs = [p.strip() for p in raw.split(",") if p.strip()]
    elif isinstance(raw, list):
        langs = [str(p).strip() for p in raw if str(p).strip()]
    else:
        langs = [str(github_cfg.get("language", "Python") or "Python")]
    seen = set()
    out = []
    for lang in langs:
        key = lang.lower()
        if key not in seen:
            seen.add(key)
            out.append(lang)
    return out or ["Python"]

def _repo_passes_universe(repo: dict[str, Any], settings: Settings) -> tuple[bool, str]:
    cfg = settings.config
    min_stars = int(cfg.get("github", {}).get("min_stars", 200) or 200)
    if repo.get("archived"):
        return False, "repo_filter:archived"
    if repo.get("fork"):
        return False, "repo_filter:fork"
    if int(repo.get("stargazers_count") or repo.get("stars") or 0) < min_stars:
        return False, f"repo_filter:stars_below_{min_stars}"
    if repo.get("has_issues") is False:
        return False, "repo_filter:issues_disabled"
    return True, "ok"



def _process_structural_pr_search(
    *,
    db: Database,
    gh: GitHubClient,
    settings: Settings,
    repo: dict[str, Any],
    query: str,
    stream_key: str,
    term: str,
    per_page: int,
    max_pages: int,
    start: float,
    case_count: int,
    repo_case_count: int,
    seen_prs: set[tuple[str, int]],
    use_graphql: bool,
    require_graphql_link: bool,
) -> tuple[int, int, int]:
    """Run one structural PR search query and process candidates.

    The function centralizes accounting for repo-window and repo-month modes.
    It performs only mechanical inclusion checks; no issue keyword or score is
    used here.
    """
    full_name = repo["full_name"]
    db.execute(
        """
        INSERT INTO retrieval_queries(stream_key, term, final_query, status, last_run_at, next_page, exhausted)
        VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, 1, 0)
        ON CONFLICT(final_query) DO UPDATE SET status='running', last_run_at=CURRENT_TIMESTAMP
        """,
        (stream_key, term, query),
    )
    raw_count = unique_count = processed_count = candidate_delta = duplicate_count = excluded_delta = 0
    excluded_start = int((db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": 0}).get("n") or 0)
    try:
        items = list(gh.search_issues(query, per_page=per_page, max_pages=max_pages))
        raw_count = len(items)
        for item in items:
            if _limit_reached(start, settings, 0, case_count):
                break
            if settings.limits.max_cases_per_repo and repo_case_count >= settings.limits.max_cases_per_repo:
                break
            pr_num = int(item.get("number") or 0)
            if pr_num <= 0:
                continue
            key = (full_name, pr_num)
            unique_count += 1
            if key in seen_prs:
                duplicate_count += 1
                continue
            seen_prs.add(key)
            known = _known_pr_outcomes(db, full_name, pr_num)
            if known["cases"] or known["exclusions"]:
                duplicate_count += 1
                processed_count += 1
                for case_id in _case_ids_for_pr(db, full_name, pr_num):
                    _record_case_retrieval(db, case_id, stream_key, term, query)
                continue
            hydration = _graphql_hydrate_pr(gh, full_name, pr_num, enabled=use_graphql)
            prefetched_links = _same_repo_graphql_issue_links(hydration, full_name)
            if require_graphql_link and not prefetched_links:
                db.log_excluded_case(full_name, None, pr_num, "no_same_repo_linked_issue", "GraphQL closingIssuesReferences had no same-repo issue")
                processed_count += 1
                continue
            try:
                pr = gh.get(f"/repos/{full_name}/pulls/{pr_num}")
                old = case_count
                processed_count += 1
                case_count, repo_case_count = _process_pr(
                    db=db,
                    gh=gh,
                    settings=settings,
                    repo=repo,
                    pr=pr,
                    start=start,
                    case_count=case_count,
                    repo_case_count=repo_case_count,
                    prefetched_links=prefetched_links,
                )
                new_cases = max(0, case_count - old)
                candidate_delta += new_cases
                for case_id in _case_ids_for_pr(db, full_name, pr_num):
                    _record_case_retrieval(db, case_id, stream_key, term, query)
            except Exception as exc:
                processed_count += 1
                log.warning("Skipping structural PR %s#%s after processing failure: %s", full_name, pr_num, exc)
                db.log_excluded_case(full_name, None, pr_num, "processing_error", str(exc))
    except GitHubSecondaryRateLimit as exc:
        db.execute("UPDATE retrieval_queries SET status='rate_limited', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(exc)[:1000], query))
        # Do not sleep for minutes here. The client already tried paced retries.
        # Stop this collection run cleanly; a later run resumes from cached state
        # and avoids keeping the process parked for a two-minute secondary wait.
        log.warning("Secondary GitHub limit on structural query; ending this pass early: %s", exc)
        return case_count, repo_case_count, -1
    except Exception as exc:
        db.execute("UPDATE retrieval_queries SET status='error', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(exc)[:1000], query))
        log.warning("Structural PR query failed %r: %s", query, exc)
    finally:
        excluded_end = int((db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": excluded_start}).get("n") or 0)
        excluded_delta = max(0, excluded_end - excluded_start)
        db.execute(
            """
            UPDATE retrieval_queries
            SET raw_count=COALESCE(raw_count,0)+?,
                unique_count=COALESCE(unique_count,0)+?,
                processed_count=COALESCE(processed_count,0)+?,
                candidate_count=COALESCE(candidate_count,0)+?,
                duplicate_count=COALESCE(duplicate_count,0)+?,
                excluded_count=COALESCE(excluded_count,0)+?,
                status=CASE WHEN status='running' THEN 'ok' ELSE status END,
                exhausted=1,
                last_run_at=CURRENT_TIMESTAMP
            WHERE final_query=?
            """,
            (raw_count, unique_count, processed_count, candidate_delta, duplicate_count, excluded_delta, query),
        )
    return case_count, repo_case_count, raw_count


def _collect_repo_month_pr_search(db: Database, gh: GitHubClient, settings: Settings, start: float, initial_case_count: int = 0) -> int:
    """Downstream-first collection frame.

    1. Build/replay a repository universe from objective repo-level queries.
    2. For each repo/month stratum, search structurally for merged PRs linked to issues.
    3. Hydrate PR candidates, mechanically enforce same-repo linked issue, then
       create cases only when approved downstream workers have an artifact to run on.

    No issue-text keyword bucket is used for inclusion.
    """
    cfg = settings.config
    collection = cfg.get("collection", {}) or {}
    per_page = int(collection.get("repo_month_per_page", collection.get("targeted_per_page", 50)) or 50)
    max_pages = int(collection.get("repo_month_max_pages", 2) or 2)
    pushed_since = str(collection.get("repo_universe_pushed_since", "2024-01-01") or "2024-01-01")
    languages = _github_languages(settings)
    language = languages[0]
    seed = _random_seed(settings)
    repo_strategy = _sample_strategy(settings, "repo_sample_strategy", "random")
    repo_shard_count = int(collection.get("repo_shard_count", 1) or 1)
    repo_shard_index = int(collection.get("repo_shard_index", 0) or 0)
    month_shard_count = int(collection.get("month_shard_count", 1) or 1)
    month_shard_index = int(collection.get("month_shard_index", 0) or 0)
    use_graphql = bool(collection.get("use_graphql_hydration", True))
    require_graphql_link = bool(collection.get("require_graphql_same_repo_link", False))
    case_count = initial_case_count
    repo_count = 0
    bot_authors = _bot_author_terms(settings)
    diagnostic_cases_start = int((db.one("SELECT COUNT(*) AS n FROM cases") or {"n": 0}).get("n") or 0)
    diagnostic_excluded_start = int((db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": 0}).get("n") or 0)

    lookback_start_cfg = str(collection.get("lookback_start", LOOKBACK_START_DATE) or LOOKBACK_START_DATE)
    configured_lookback_months = int(
        collection.get(
            "lookback_months",
            12,
        )
        or 12
    )

    # Cap the configured upper bound at the number of calendar months that
    # actually exist between lookback_start and the current UTC month.
    from datetime import datetime as _repo_window_datetime
    from datetime import timezone as _repo_window_timezone

    try:
        _repo_start = _repo_window_datetime.strptime(
            lookback_start_cfg[:10],
            "%Y-%m-%d",
        ).date()

        _repo_today = _repo_window_datetime.now(
            _repo_window_timezone.utc
        ).date()

        _available_lookback_months = (
            (_repo_today.year - _repo_start.year) * 12
            + (_repo_today.month - _repo_start.month)
            + 1
        )
    except (TypeError, ValueError):
        _available_lookback_months = configured_lookback_months

    lookback_months_cfg = max(
        1,
        min(
            configured_lookback_months,
            max(
                1,
                _available_lookback_months,
            ),
        ),
    )

    log.info(
        "Repository lookback window capped. "
        "start=%s configured_months=%s effective_months=%s",
        lookback_start_cfg,
        configured_lookback_months,
        lookback_months_cfg,
    )

    windows = month_windows(
        lookback_start_cfg,
        lookback_months_cfg,
    )

    windows = [
        window
        for window in windows
        if shard_accept(
            window.start,
            shard_count=month_shard_count,
            shard_index=month_shard_index,
        )
    ]

    full_window_for_seed = lookback_window(
        lookback_start_cfg,
        lookback_months_cfg,
    )

    repo_pool: list[dict[str, Any]] = []
    active_repo_names: set[str] = set()

    # Seed this shard from repositories already present in the active
    # evaluation database. The shard database itself starts empty.
    existing_seed_path = str(
        __import__("os").environ.get(
            "MINING_REPO_SEED_DB",
            "",
        )
        or ""
    ).strip()

    existing_seed_names = (
        load_existing_repo_seed_names(
            existing_seed_path
        )
        if existing_seed_path
        else []
    )

    existing_seed_eligible = 0
    existing_seed_rejected = 0
    existing_seed_fetch_errors = 0

    seed_pool_limit = 0

    if settings.limits.max_repos:
        seed_pool_limit = (
            settings.limits.max_repos
            * _pool_multiplier(
                settings,
                "repo_sample_pool_multiplier",
                4,
            )
        )

    for full_name in existing_seed_names:
        if not shard_accept(
            full_name,
            shard_count=repo_shard_count,
            shard_index=repo_shard_index,
        ):
            continue

        try:
            repo = gh.get(
                f"/repos/{full_name}"
            )
        except Exception as exc:
            existing_seed_fetch_errors += 1

            db.log_excluded_case(
                full_name,
                None,
                None,
                "existing_repo_seed_fetch_error",
                str(exc),
            )

            continue

        ok, reason = _repo_passes_universe(
            repo,
            settings,
        )

        if not ok:
            existing_seed_rejected += 1

            db.log_excluded_case(
                full_name,
                None,
                None,
                reason.split(":", 1)[0],
                reason,
            )

            continue

        repo_pool.append(repo)
        active_repo_names.add(full_name)
        existing_seed_eligible += 1

        if (
            seed_pool_limit
            and len(repo_pool) >= seed_pool_limit
        ):
            break

    existing_seed_loaded = bool(repo_pool)

    if existing_seed_path:
        seed_query_key = (
            "existing-db:"
            + existing_seed_path
            + ":shard="
            + str(repo_shard_index)
            + "/"
            + str(repo_shard_count)
        )

        db.execute(
            '''
            INSERT INTO retrieval_queries(
                stream_key,
                term,
                final_query,
                raw_count,
                unique_count,
                eligible_count,
                candidate_count,
                processed_count,
                excluded_count,
                status,
                exhausted,
                last_run_at
            )
            VALUES (
                'existing_repo_seed',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                'ok',
                1,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT(final_query) DO UPDATE SET
                raw_count=excluded.raw_count,
                unique_count=excluded.unique_count,
                eligible_count=excluded.eligible_count,
                candidate_count=excluded.candidate_count,
                processed_count=excluded.processed_count,
                excluded_count=excluded.excluded_count,
                status='ok',
                exhausted=1,
                last_error=NULL,
                last_run_at=CURRENT_TIMESTAMP
            ''',
            (
                existing_seed_path,
                seed_query_key,
                len(existing_seed_names),
                len(existing_seed_names),
                existing_seed_eligible,
                existing_seed_eligible,
                (
                    existing_seed_eligible
                    + existing_seed_rejected
                    + existing_seed_fetch_errors
                ),
                (
                    existing_seed_rejected
                    + existing_seed_fetch_errors
                ),
            ),
        )

        _pipeline_event(
            db,
            "existing_repo_seed_loaded",
            (
                f"path={existing_seed_path} "
                f"names={len(existing_seed_names)} "
                f"eligible={existing_seed_eligible} "
                f"rejected={existing_seed_rejected} "
                f"fetch_errors={existing_seed_fetch_errors} "
                f"shard={repo_shard_index}/{repo_shard_count}"
            ),
        )

        log.info(
            "Existing repository seed loaded. "
            "path=%s names=%s eligible=%s rejected=%s "
            "fetch_errors=%s shard=%s/%s",
            existing_seed_path,
            len(existing_seed_names),
            existing_seed_eligible,
            existing_seed_rejected,
            existing_seed_fetch_errors,
            repo_shard_index,
            repo_shard_count,
        )

    # Active structural seed: one global, keyword-free PR search over the full
    # lookback window to find repos that are demonstrably producing merged
    # issue-linked PRs. This is only a repository-universe accelerator; actual
    # case construction remains repo-scoped and same-repo/tool-applicable.
    if bool(collection.get("active_repo_seed", True)):
        try:
            active_pages = max(1, int(collection.get("active_repo_seed_max_pages", 2) or 2))
            active_per_page = max(1, min(100, int(collection.get("active_repo_seed_per_page", 100) or 100)))
        except (TypeError, ValueError):
            active_pages, active_per_page = 2, 100
        try:
            min_stars = int(cfg.get("github", {}).get("min_stars", 200) or 200)
        except (TypeError, ValueError):
            min_stars = 200
        raw_seed_total = 0
        seed_repos: set[str] = set()
        for seed_language in languages:
            active_query = global_active_pr_query(full_window_for_seed, language=seed_language, min_stars=min_stars, bot_authors=bot_authors)
            db.execute(
                """
                INSERT INTO retrieval_queries(stream_key, term, final_query, status, last_run_at)
                VALUES ('active_repo_seed', ?, ?, 'running', CURRENT_TIMESTAMP)
                ON CONFLICT(final_query) DO UPDATE SET status='running', last_run_at=CURRENT_TIMESTAMP
                """,
                (f"{seed_language}:{full_window_for_seed.start}..{full_window_for_seed.end}", active_query),
            )
            raw_seed = 0
            try:
                for item in gh.search_issues(active_query, per_page=active_per_page, max_pages=active_pages):
                    raw_seed += 1
                    raw_seed_total += 1
                    repo_url = item.get("repository_url") or ""
                    if not repo_url:
                        continue
                    full_name = _repo_full_name_from_url(repo_url)
                    if not full_name or full_name in seed_repos:
                        continue
                    if not shard_accept(full_name, shard_count=repo_shard_count, shard_index=repo_shard_index):
                        continue
                    try:
                        repo = gh.get(f"/repos/{full_name}")
                    except Exception as exc:
                        db.log_excluded_case(full_name, None, item.get("number"), "repo_seed_fetch_error", str(exc))
                        continue
                    ok, reason = _repo_passes_universe(repo, settings)
                    if not ok:
                        db.log_excluded_case(full_name, None, item.get("number"), reason.split(":", 1)[0], reason)
                        continue
                    seed_repos.add(full_name)
                    active_repo_names.add(full_name)
                    repo_pool.append(repo)
                    if settings.limits.max_repos and len(seed_repos) >= settings.limits.max_repos * _pool_multiplier(settings, "repo_sample_pool_multiplier", 4):
                        break
                db.execute(
                    """
                    UPDATE retrieval_queries
                    SET status='ok', raw_count=?, unique_count=?, exhausted=1, last_run_at=CURRENT_TIMESTAMP
                    WHERE final_query=?
                    """,
                    (raw_seed, len(seed_repos), active_query),
                )
            except GitHubSecondaryRateLimit as exc:
                db.execute("UPDATE retrieval_queries SET status='rate_limited', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(exc)[:1000], active_query))
                log.warning("Active repo seed hit secondary limit for language %s; continuing with collected seed repos: %s", seed_language, exc)
                break
            except Exception as exc:
                db.execute("UPDATE retrieval_queries SET status='error', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(exc)[:1000], active_query))
                log.warning("Active repo seed failed for language %s; continuing: %s", seed_language, exc)
            if settings.limits.max_repos and len(seed_repos) >= settings.limits.max_repos * _pool_multiplier(settings, "repo_sample_pool_multiplier", 4):
                break
        log.info("Active repo seed found %s repos from %s structural PR hits across languages=%s", len(seed_repos), raw_seed_total, ",".join(languages))

    repo_queries = []

    # Generic star-band discovery is a fallback only. Do not rediscover
    # unrelated repositories when the active database supplied a seed.
    if not existing_seed_loaded:
        for repo_language in languages:
            repo_queries.extend(
                star_band_queries(
                    language=repo_language,
                    pushed_since=pushed_since,
                )
            )
    for rq in repo_queries:
        if settings.limits.max_seconds and time.time() - start >= settings.limits.max_seconds:
            break
        db.execute(
            """
            INSERT INTO retrieval_queries(stream_key, term, final_query, status, last_run_at)
            VALUES ('repo_universe', ?, ?, 'running', CURRENT_TIMESTAMP)
            ON CONFLICT(final_query) DO UPDATE SET status='running', last_run_at=CURRENT_TIMESTAMP
            """,
            (rq, rq),
        )
        try:
            for repo in gh.search_repos(rq, per_page=per_page):
                full_name = repo.get("full_name") or ""
                if not full_name:
                    continue
                if not shard_accept(full_name, shard_count=repo_shard_count, shard_index=repo_shard_index):
                    continue
                ok, reason = _repo_passes_universe(repo, settings)
                if not ok:
                    db.log_excluded_case(full_name, None, None, reason.split(":", 1)[0], reason)
                    continue
                repo_pool.append(repo)
                if settings.limits.max_repos and len(repo_pool) >= settings.limits.max_repos * _pool_multiplier(settings, "repo_sample_pool_multiplier", 4):
                    break
            db.execute("UPDATE retrieval_queries SET status='ok', exhausted=1, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (rq,))
        except Exception as exc:
            db.execute("UPDATE retrieval_queries SET status='error', last_error=?, last_run_at=CURRENT_TIMESTAMP WHERE final_query=?", (str(exc)[:1000], rq))
            log.warning("Repo universe query failed %r: %s", rq, exc)
        if settings.limits.max_repos and len(repo_pool) >= settings.limits.max_repos * _pool_multiplier(settings, "repo_sample_pool_multiplier", 4):
            break

    # Deduplicate while preserving first repo object.
    by_repo: dict[str, dict[str, Any]] = {}
    for repo in repo_pool:
        by_repo.setdefault(repo["full_name"], repo)
    repos = list(by_repo.values())
    if repo_strategy in {"active_first", "hybrid", "active_then_random"}:
        active = [r for r in repos if r.get("full_name") in active_repo_names]
        rest = [r for r in repos if r.get("full_name") not in active_repo_names]
        # Shuffle both groups. GitHub search tends to place one busy repo first;
        # preserving that order defeated wide-first discovery in practice.
        active = _stable_shuffle(active, seed, "repo_active_seed")
        rest = _stable_shuffle(rest, seed, "repo_month_repo_rest")
        repos = active + rest
    elif repo_strategy == "random":
        repos = _stable_shuffle(repos, seed, "repo_month_repo")
    if settings.limits.max_repos:
        repos = repos[: settings.limits.max_repos]

    retrieval_mode = str(collection.get("retrieval_mode", "repo_window_pr_search") or "repo_window_pr_search").lower()
    window_mode = retrieval_mode in {"repo_window", "repo_window_pr_search", "repo_window_adaptive", "downstream_first"}
    if window_mode:
        # Reuse the already capped range. Re-reading the raw configuration
        # here previously converted lookback_months=120 into an end date
        # ten years in the future.
        full_window = full_window_for_seed
        per_page = int(collection.get("repo_window_per_page", per_page) or per_page)
        max_pages = int(collection.get("repo_window_max_pages", max_pages) or max_pages)
        split_threshold = int(collection.get("repo_window_split_threshold", per_page * max_pages) or (per_page * max_pages))
        log.info(
            "Repo-window collection starting: repos=%s window=%s..%s shard=%s/%s per_page=%s max_pages=%s split_threshold=%s",
            len(repos), full_window.start, full_window.end, repo_shard_index, repo_shard_count, per_page, max_pages, split_threshold,
        )
    else:
        log.info("Repo-month collection starting: repos=%s months=%s shard=%s/%s month_shard=%s/%s", len(repos), len(windows), repo_shard_index, repo_shard_count, month_shard_index, month_shard_count)

    seen_prs: set[tuple[str, int]] = set()
    stop_after_secondary = False
    for repo in repos:
        if stop_after_secondary or _limit_reached(start, settings, repo_count, case_count):
            break
        full_name = repo["full_name"]
        repo_count += 1
        db.insert_or_get_repo(repo)
        repo_case_count = 0

        if window_mode:
            q = repo_window_pr_query(full_name, full_window, bot_authors=bot_authors)
            term = f"{full_name}:{full_window.start}..{full_window.end}"
            case_count, repo_case_count, raw_count = _process_structural_pr_search(
                db=db,
                gh=gh,
                settings=settings,
                repo=repo,
                query=q,
                stream_key="repo_window",
                term=term,
                per_page=per_page,
                max_pages=max_pages,
                start=start,
                case_count=case_count,
                repo_case_count=repo_case_count,
                seen_prs=seen_prs,
                use_graphql=use_graphql,
                require_graphql_link=require_graphql_link,
            )
            if raw_count < 0:
                stop_after_secondary = True
                break
            # Discovery mode must stay wide-first. A saturated repo should not
            # immediately consume another 12 searches and trigger secondary rate
            # limits. Only split saturated repos when explicitly requested for an
            # exhaustive/final pass.
            exhaustive_split = bool(collection.get("repo_window_exhaustive_split", collection.get("exhaustive_split", False)))
            if raw_count >= split_threshold and not exhaustive_split:
                log.info("Repo-window result saturated for %s (%s hits); discovery mode records saturation and moves to next repo", full_name, raw_count)
                _pipeline_event(db, "repo_window_saturated", f"{full_name} raw_count={raw_count} split_threshold={split_threshold}")
            if exhaustive_split and raw_count >= split_threshold and len(windows) > 1 and not _limit_reached(start, settings, repo_count, case_count):
                log.info("Repo-window result saturated for %s (%s hits); exhaustive split by month enabled", full_name, raw_count)
                for window in windows:
                    if _limit_reached(start, settings, repo_count, case_count):
                        break
                    if settings.limits.max_cases_per_repo and repo_case_count >= settings.limits.max_cases_per_repo:
                        break
                    q = repo_month_pr_query(full_name, window, bot_authors=bot_authors)
                    term = f"{full_name}:{window.start}..{window.end}"
                    case_count, repo_case_count, month_raw = _process_structural_pr_search(
                        db=db,
                        gh=gh,
                        settings=settings,
                        repo=repo,
                        query=q,
                        stream_key="repo_month_adaptive",
                        term=term,
                        per_page=per_page,
                        max_pages=max_pages,
                        start=start,
                        case_count=case_count,
                        repo_case_count=repo_case_count,
                        seen_prs=seen_prs,
                        use_graphql=use_graphql,
                        require_graphql_link=require_graphql_link,
                    )
                    if month_raw < 0:
                        stop_after_secondary = True
                        break
            continue

        for window in windows:
            if _limit_reached(start, settings, repo_count, case_count):
                break
            if settings.limits.max_cases_per_repo and repo_case_count >= settings.limits.max_cases_per_repo:
                break
            q = repo_month_pr_query(full_name, window, bot_authors=bot_authors)
            term = f"{full_name}:{window.start}..{window.end}"
            case_count, repo_case_count, raw_count = _process_structural_pr_search(
                db=db,
                gh=gh,
                settings=settings,
                repo=repo,
                query=q,
                stream_key="repo_month",
                term=term,
                per_page=per_page,
                max_pages=max_pages,
                start=start,
                case_count=case_count,
                repo_case_count=repo_case_count,
                seen_prs=seen_prs,
                use_graphql=use_graphql,
                require_graphql_link=require_graphql_link,
            )
            if raw_count < 0:
                stop_after_secondary = True
                break
    diagnostic_cases_end = int((db.one("SELECT COUNT(*) AS n FROM cases") or {"n": diagnostic_cases_start}).get("n") or 0)
    diagnostic_excluded_end = int((db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {"n": diagnostic_excluded_start}).get("n") or 0)
    reason_rows = db.query(
        """
        SELECT reason, COUNT(*) AS n
        FROM excluded_cases
        WHERE id > ?
        GROUP BY reason
        ORDER BY n DESC, reason ASC
        LIMIT 12
        """,
        (diagnostic_excluded_start,),
    )
    reason_summary = ", ".join(f"{r['reason']}={r['n']}" for r in reason_rows) or "none"
    log.info(
        "Structural PR collection complete. repos_searched=%s cases_total=%s new_cases=%s new_exclusions=%s exclusions_by_reason=%s",
        repo_count,
        case_count,
        max(0, diagnostic_cases_end - diagnostic_cases_start),
        max(0, diagnostic_excluded_end - diagnostic_excluded_start),
        reason_summary,
    )
    _pipeline_event(db, "collection_diagnostics", f"repos_searched={repo_count} new_cases={max(0, diagnostic_cases_end - diagnostic_cases_start)} new_exclusions={max(0, diagnostic_excluded_end - diagnostic_excluded_start)} reasons={reason_summary}")
    return case_count

def collect(settings: Settings) -> None:
    db = Database(settings.db_path)
    cfg = settings.config
    cache_cfg = cfg.get("cache", {})
    gh = GitHubClient(
        settings.github_token,
        cache_dir=cache_cfg.get("github_cache_dir", "data/cache/github_api"),
        cache_enabled=cache_cfg.get("github_api", True),
        force_refresh=cache_cfg.get("force_refresh", False),
        secondary_wait_seconds=int(cfg.get("collection", {}).get("ai_search", {}).get("secondary_wait_seconds", 90)),
        max_secondary_retries=int(cfg.get("collection", {}).get("ai_search", {}).get("max_secondary_retries", 1)),
        rate_db_path=None,  # disabled for shard collectors; avoids sqlite rate-db failures
        min_remaining=int(cfg.get("github", {}).get("min_remaining", 100)),
        search_min_remaining=int(cfg.get("github", {}).get("search_min_remaining", 2)),
        search_min_interval_seconds=float(cfg.get("github", {}).get("search_min_interval_seconds", 2.25) or 0),
        core_min_interval_seconds=float(cfg.get("github", {}).get("core_min_interval_seconds", 0.0) or 0),
        jitter_seconds=float(cfg.get("github", {}).get("request_jitter_seconds", 0.5) or 0),
    )
    start = time.time()

    retrieval_mode = str(cfg.get("collection", {}).get("retrieval_mode", "targeted")).lower()
    ai_only = bool(cfg.get("collection", {}).get("ai_only", False))
    discovery = str(cfg.get("collection", {}).get("ai_discovery", "hybrid")).lower()
    if retrieval_mode in {"repo_month", "repo_month_pr_search", "repo_window", "repo_window_pr_search", "repo_window_adaptive", "repo_universe", "downstream_first"}:
        cases = _collect_repo_month_pr_search(db, gh, settings, start)
    elif retrieval_mode in {"targeted", "streams", "stream", "targeted_pr_search", "wide", "wide_first"}:
        cases = _collect_targeted_stream_search(db, gh, settings, start)
    elif ai_only and discovery in {"search", "hybrid"}:
        log.info("Starting AI-focused marker search. This uses agentic markers only; it does not seed AI-specific repos.")
        cases = _collect_ai_search(db, gh, settings, start)
        if discovery == "hybrid" and not _limit_reached(start, settings, 0, cases) and bool(cfg.get("collection", {}).get("repo_walk_enabled", False)):
            log.info("Continuing with AI-filtered repo walk over normal GitHub search results. Cases must still contain agentic markers.")
            cases = _collect_repo_walk(db, gh, settings, start, initial_case_count=cases)
    else:
        if bool(cfg.get("collection", {}).get("repo_walk_enabled", False)):
            cases = _collect_repo_walk(db, gh, settings, start)
        else:
            log.info("Repo-walk is disabled; using targeted PR search instead. retrieval_mode=%s", retrieval_mode)
            cases = _collect_targeted_stream_search(db, gh, settings, start)
    log.info("Collection complete. cases=%s", cases)
