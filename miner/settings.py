from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT


def _project_path_from_env(env_name: str, default_relative: str) -> Path:
    """Resolve config/db paths without relying on the process current directory.

    Streamlit can be launched from a directory that later disappears or from an
    arbitrary working directory.  Calling Path(...).resolve() on a relative path
    then touches os.getcwd(), which can raise FileNotFoundError.  Relative paths
    are therefore resolved from the project root, not from cwd.
    """
    raw = os.getenv(env_name, default_relative)
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def _env_int(name: str, default: int | None = None) -> int | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class RuntimeLimits:
    max_repos: int | None
    max_prs: int | None
    max_cases: int | None
    max_cases_per_repo: int | None
    max_seconds: int | None


@dataclass(frozen=True)
class Settings:
    config_path: Path
    db_path: Path
    github_token: str | None
    config: dict[str, Any]
    limits: RuntimeLimits


def load_settings() -> Settings:
    config_path = _project_path_from_env("CONFIG", "config.yml")
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    db_path = _project_path_from_env("DB_PATH", config.get("database", {}).get("path", "data/miner.db"))
    github_token = os.getenv("GITHUB_TOKENS") or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or None

    github_cfg = config.setdefault("github", {})

    val = os.getenv("GITHUB_SECONDARY_COOLDOWN_PATH")
    if val is not None and val != "":
        github_cfg["secondary_cooldown_path"] = val.strip()

    for env_name, key in (
        ("GITHUB_SECONDARY_COOLDOWN_BASE_SECONDS", "secondary_cooldown_base_seconds"),
        ("GITHUB_SECONDARY_COOLDOWN_MAX_SECONDS", "secondary_cooldown_max_seconds"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            try:
                github_cfg[key] = int(val)
            except ValueError:
                pass

    val = os.getenv("GITHUB_LANGUAGE")
    if val is not None and val != "":
        github_cfg["language"] = val.strip()
        github_cfg["languages"] = [val.strip()]

    val = os.getenv("GITHUB_LANGUAGES")
    if val is not None and val != "":
        langs = [p.strip() for p in val.split(",") if p.strip()]
        github_cfg["languages"] = langs
        if langs and not os.getenv("GITHUB_LANGUAGE"):
            github_cfg["language"] = langs[0]

    # Runtime toggles for fast/expensive passes.
    scanners = config.setdefault("scanners", {})
    for env_name, key in (("SCAN_CODEQL", "codeql"), ("SCAN_GITLEAKS", "gitleaks"), ("SCAN_OSV", "osv"), ("SCAN_DEPENDENCY_DOWNGRADE", "dependency_downgrade"), ("SCAN_SEMGREP", "semgrep")):
        val = os.getenv(env_name)
        if val is not None and val != "":
            scanners[key] = val.strip().lower() in {"1", "true", "yes", "on"}


    cache = config.setdefault("cache", {})
    for env_name, key in (("GITHUB_CACHE", "github_api"), ("FORCE_REFRESH", "force_refresh"), ("FORCE_RESCAN", "force_rescan")):
        val = os.getenv(env_name)
        if val is not None and val != "":
            cache[key] = val.strip().lower() in {"1", "true", "yes", "on"}

    collection = config.setdefault("collection", {})
    val = os.getenv("AI_ONLY")
    if val is not None and val != "":
        collection["ai_only"] = val.strip().lower() in {"1", "true", "yes", "on", "explicit"}

    val = os.getenv("AI_DISCOVERY")
    if val is not None and val != "":
        collection["ai_discovery"] = val.strip().lower()

    for env_name, key in (
        ("RETRIEVAL_MODE", "retrieval_mode"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            collection[key] = val.strip().lower()

    for env_name, key in (
        ("REPO_SAMPLE_STRATEGY", "repo_sample_strategy"),
        ("CASE_SAMPLE_STRATEGY", "case_sample_strategy"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            collection[key] = val.strip().lower()

    val = os.getenv("LOOKBACK_START")
    if val is not None and val != "":
        collection["lookback_start"] = val.strip()

    for env_name, key in (
        ("RANDOM_SEED", "random_seed"),
        ("REPO_SAMPLE_POOL_MULTIPLIER", "repo_sample_pool_multiplier"),
        ("CASE_SAMPLE_POOL_MULTIPLIER", "case_sample_pool_multiplier"),
        ("LOOKBACK_MONTHS", "lookback_months"),
        ("REPO_SHARD_COUNT", "repo_shard_count"),
        ("REPO_SHARD_INDEX", "repo_shard_index"),
        ("MONTH_SHARD_COUNT", "month_shard_count"),
        ("MONTH_SHARD_INDEX", "month_shard_index"),
        ("REPO_MONTH_MAX_PAGES", "repo_month_max_pages"),
        ("REPO_MONTH_PER_PAGE", "repo_month_per_page"),
        ("REPO_WINDOW_MAX_PAGES", "repo_window_max_pages"),
        ("REPO_WINDOW_PER_PAGE", "repo_window_per_page"),
        ("REPO_WINDOW_SPLIT_THRESHOLD", "repo_window_split_threshold"),
        ("ISSUE_MIN_BODY_CHARS", "issue_min_body_chars"),
        ("ACTIVE_REPO_SEED_MAX_PAGES", "active_repo_seed_max_pages"),
        ("ACTIVE_REPO_SEED_PER_PAGE", "active_repo_seed_per_page"),
        ("MAX_CHANGED_FILES_FOR_EVIDENCE", "max_changed_files_for_evidence"),
        ("MAX_LINKED_ISSUES_PER_PR_FOR_EVIDENCE", "max_linked_issues_per_pr_for_evidence"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            try:
                collection[key] = int(val)
            except ValueError:
                pass

    val = os.getenv("FETCH_COMMIT_MESSAGES_FOR_AI")
    if val is not None and val != "":
        collection["fetch_commit_messages_for_ai"] = val.strip().lower() in {"1", "true", "yes", "on"}

    for env_name, key in (
        ("USE_GRAPHQL_HYDRATION", "use_graphql_hydration"),
        ("REQUIRE_GRAPHQL_SAME_REPO_LINK", "require_graphql_same_repo_link"),
        ("REQUIRE_ISSUE_QUALITY_FILTER", "require_issue_quality_filter"),
        ("ACTIVE_REPO_SEED", "active_repo_seed"),
        ("REQUIRE_PRIMARY_WORKER", "require_primary_worker"),
        ("REQUIRE_HIGH_YIELD_SURFACE", "require_high_yield_surface"),
        ("REPO_WINDOW_EXHAUSTIVE_SPLIT", "repo_window_exhaustive_split"),
        ("EXHAUSTIVE_SPLIT", "exhaustive_split"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            collection[key] = val.strip().lower() in {"1", "true", "yes", "on"}

    ai_search = collection.setdefault("ai_search", {})
    for env_name, key in (
        ("AI_PROFILE", "profile"),
        ("MAX_SEARCH_TERMS", "max_marker_queries"),
        ("SEARCH_PER_PAGE", "per_page"),
        ("SEARCH_PAUSE_SECONDS", "pause_seconds"),
        ("SECONDARY_WAIT_SECONDS", "secondary_wait_seconds"),
        ("MAX_SECONDARY_RETRIES", "max_secondary_retries"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            if key in {"max_marker_queries", "per_page", "pause_seconds", "secondary_wait_seconds", "max_secondary_retries"}:
                try:
                    ai_search[key] = int(val)
                except ValueError:
                    pass
            else:
                ai_search[key] = val.strip()

    scan_cfg = config.setdefault("scan", {})
    val = os.getenv("SCAN_AI_ONLY")
    if val is not None and val != "":
        scan_cfg["ai_only"] = val.strip().lower() in {"1", "true", "yes", "on", "explicit"}

    val = os.getenv("CODEQL_MAX_PER_RUN")
    if val is not None and val != "":
        try:
            scan_cfg["codeql_max_per_run"] = int(val)
        except ValueError:
            pass

    val = os.getenv("CODEQL_TIMEOUT_SECONDS")
    if val is not None and val != "":
        try:
            config.setdefault("scanners", {})["codeql_timeout_seconds"] = int(val)
        except ValueError:
            pass

    val = os.getenv("SEMGREP_TIMEOUT_SECONDS")
    if val is not None and val != "":
        try:
            config.setdefault("scanners", {})["semgrep_timeout_seconds"] = int(val)
        except ValueError:
            pass

    val = os.getenv("SEMGREP_CONFIG")
    if val is not None and val != "":
        config.setdefault("scanners", {})["semgrep_config"] = val.strip()

    val = os.getenv("CODEQL_TRIGGER")
    if val is not None and val != "":
        config.setdefault("scanners", {})["codeql_trigger"] = val.strip().lower()

    val = os.getenv("CODEQL_LANGUAGE")
    if val is not None and val != "":
        config.setdefault("scanners", {})["codeql_language"] = val.strip().lower()

    val = os.getenv("CODEQL_QUERY_SUITE")
    if val is not None and val != "":
        config.setdefault("scanners", {})["codeql_query_suite"] = val.strip()

    val = os.getenv("CODEQL_BUILD_MODE")
    if val is not None and val != "":
        config.setdefault("scanners", {})["codeql_build_mode"] = val.strip().lower()


    val = os.getenv("GITHUB_MIN_REMAINING")
    if val is not None and val != "":
        try:
            config.setdefault("github", {})["min_remaining"] = int(val)
        except ValueError:
            pass

    val = os.getenv("GITHUB_SEARCH_MIN_REMAINING")
    if val is not None and val != "":
        try:
            config.setdefault("github", {})["search_min_remaining"] = int(val)
        except ValueError:
            pass

    for env_name, key in (
        ("GITHUB_SEARCH_MIN_INTERVAL_SECONDS", "search_min_interval_seconds"),
        ("GITHUB_CORE_MIN_INTERVAL_SECONDS", "core_min_interval_seconds"),
        ("GITHUB_REQUEST_JITTER_SECONDS", "request_jitter_seconds"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            try:
                config.setdefault("github", {})[key] = float(val)
            except ValueError:
                pass

    val = os.getenv("MIN_STARS")
    if val is not None and val != "":
        try:
            config.setdefault("github", {})["min_stars"] = int(val)
        except ValueError:
            pass

    filters_cfg = config.setdefault("filters", {})
    val = os.getenv("ISSUE_MIN_BODY_CHARS")
    if val is not None and val != "":
        try:
            filters_cfg["issue_min_body_chars"] = int(val)
        except ValueError:
            pass
    val = os.getenv("EXCLUDE_DOCS_SCOPE_ONLY")
    if val is not None and val != "":
        filters_cfg["exclude_docs_scope_only"] = val.strip().lower() in {"1", "true", "yes", "on"}

    for env_name, key in (
        ("TARGETED_PER_PAGE", "targeted_per_page"),
        ("TARGETED_MAX_PAGES", "targeted_max_pages"),
        ("TARGETED_MAX_TERMS", "targeted_max_terms"),
        ("TARGETED_PAUSE_SECONDS", "targeted_pause_seconds"),
        ("MAX_PROCESSED_PRS_PER_REPO", "max_processed_prs_per_repo"),
        ("MAX_RAW_HITS_PER_REPO_PER_PASS", "max_raw_hits_per_repo_per_pass"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            try:
                collection[key] = int(val)
            except ValueError:
                pass

    val = os.getenv("QUERY_PHASES")
    if val is not None and val != "":
        collection["query_phases"] = [p.strip() for p in val.split(",") if p.strip()]

    val = os.getenv("REPO_WALK_ENABLED")
    if val is not None and val != "":
        collection["repo_walk_enabled"] = val.strip().lower() in {"1", "true", "yes", "on"}

    workers_cfg = config.setdefault("workers", {})
    for env_name, key in (
        ("WORKER_IDLE_SECONDS", "idle_seconds"),
        ("WORKER_MAX_LOOPS", "max_loops"),
        ("JOB_STALE_MINUTES", "job_stale_minutes"),
        ("CODEQL_STALE_MINUTES", "codeql_stale_minutes"),
    ):
        val = os.getenv(env_name)
        if val is not None and val != "":
            try:
                workers_cfg[key] = int(val)
            except ValueError:
                pass

    limits = RuntimeLimits(
        max_repos=_env_int("MAX_REPOS"),
        max_prs=_env_int("MAX_PRS"),
        max_cases=_env_int("MAX_CASES"),
        max_cases_per_repo=_env_int("MAX_CASES_PER_REPO", config.get("collection", {}).get("max_cases_per_repo", 10)),
        max_seconds=_env_int("MAX_SECONDS"),
    )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return Settings(config_path=config_path, db_path=db_path, github_token=github_token, config=config, limits=limits)
