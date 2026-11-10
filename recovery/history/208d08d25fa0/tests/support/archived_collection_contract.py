"""Allowlisted AST replay of the 2026 miner's search and dispatch functions.

TEST-ONLY. The historical collector is never imported. Its exact SHA-256 is
validated before any byte can be compiled, and only named function-def ASTs
are selected. The dispatcher runs with stub constructors; search pagination
runs on an explicit fail-closed in-memory transport. No HTTP, cluster, or
production SQLite path is available through this module.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
import logging
import math
import os
import posixpath
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.github.replay_client import GitHubAPIError, MissingFixtureError, ReplayGitHubClient
from src.db.database import Database
from tests.support.archived_pr_contract import (
    IncompleteReplayError, FixtureOnlyGitHub, load_original_process_pr,
)
import tempfile

COLLECTOR_SHA256 = "5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750"
SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py"
)
SEARCH_NAMES = (
    "_github_search_timestamp", "_parse_agentic_lookback",
    "_bounded_merged_query", "_split_agentic_window",
    "_iter_adaptive_agentic_search",
)


class FixtureSearchOnly(FixtureOnlyGitHub):
    """FixtureOnlyGitHub + Search/GraphQL methods, with no network fallback."""

    def __init__(self, client: ReplayGitHubClient):
        super().__init__(client)

    def search_issues_page(self, *args, **kwargs):
        try:
            return self._client.search_issues_page(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc

    def search_issues(self, *args, **kwargs):
        try:
            yield from self._client.search_issues(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc

    def is_search_1000_limit_error(self, exc):
        return self._client.is_search_1000_limit_error(exc)


def _extract(names: tuple[str, ...], scope: dict[str, Any]) -> dict[str, Any]:
    raw = SOURCE_PATH.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != COLLECTOR_SHA256:
        raise ValueError(f"Historical collector source hash mismatch: {actual}")
    parsed = ast.parse(raw, filename=str(SOURCE_PATH))
    chosen = {n.name: n for n in parsed.body
              if isinstance(n, ast.FunctionDef) and n.name in names}
    if set(chosen) != set(names):
        raise ValueError(f"Missing historical functions: {set(names)-set(chosen)}")
    if any(node.decorator_list for node in chosen.values()):
        raise ValueError("Decorated original functions require separate audit")
    code = compile(
        ast.fix_missing_locations(ast.Module(body=[chosen[n] for n in names], type_ignores=[])),
        str(SOURCE_PATH), "exec", flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    scope = dict(scope)
    scope.update({"__name__": "_offline_archived_collection_contract", "__builtins__": __builtins__})
    exec(code, scope, scope)
    return scope


def load_original_adaptive_search() -> dict[str, Any]:
    """Return the five exact original date-window/search functions for fixtures."""
    scope = _extract(SEARCH_NAMES, {
        "datetime": datetime, "timezone": timezone, "timedelta": timedelta,
        "math": math, "re": re, "GitHubClient": FixtureSearchOnly,
    })
    original = scope["_iter_adaptive_agentic_search"]

    def checked_search(gh, *args, **kwargs):
        if not isinstance(gh, FixtureSearchOnly):
            raise TypeError("Only the in-memory GitHub replay client is accepted")
        yield from original(gh, *args, **kwargs)

    scope["run"] = checked_search
    return scope


class DispatchSpies:
    """Dependencies deliberately prevented from executing original IO handlers."""

    def __init__(self, *, limiter=None):
        self.calls: list[tuple[str, tuple, dict]] = []
        self.limits = []
        self.limiter = limiter or (lambda *args, **kwargs: False)
        self.client_kwargs: dict[str, Any] = {}
        self.client_token_seen = False
        self.fake_environ: dict[str, str] = {}

    def database(self, path):
        if path != "fixture:database":
            raise ValueError("Only the non-SQLite synthetic database sentinel is valid")
        self.calls.append(("database_ctor", (path,), {}))
        return SimpleNamespace(fixture_database=True)

    def client(self, token, **kwargs):
        if token != "NON_SECRET_FIXTURE_TOKEN":
            raise ValueError("No real GitHub token may enter a dispatcher replay")
        self.client_token_seen = True
        self.client_kwargs = kwargs
        self.calls.append(("github_ctor", (), {}))
        return SimpleNamespace(fixture_github=True)

    def handler(self, name, result):
        def fake_handler(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return result
        return fake_handler

    def limit_reached(self, *args, **kwargs):
        self.limits.append((args, kwargs))
        return self.limiter(*args, **kwargs)


def load_original_dispatch(spies: DispatchSpies):
    """Compile collect() only with audited inert constructor/handler stubs."""
    if not isinstance(spies, DispatchSpies):
        raise TypeError("Explicit dispatch spies required")
    handler_names = {
        "_collect_repo_month_pr_search": 11,
        "_collect_targeted_stream_search": 12,
        "_collect_ai_search": 13,
        "_collect_repo_walk": 14,
    }
    scope = {
        "Database": spies.database,
        "GitHubClient": spies.client,
        "os": SimpleNamespace(environ=spies.fake_environ, path=SimpleNamespace(join=posixpath.join)),
        "time": SimpleNamespace(time=lambda: 1000.0),
        "log": logging.getLogger("arno.dispatch.fixture"),
        "_limit_reached": spies.limit_reached,
        **{name: spies.handler(name, ret) for name, ret in handler_names.items()},
    }
    return _extract(("collect",), scope)["collect"]


def fixture_settings(config=None):
    """No path or credential capable of opening a real database or remote API."""
    return SimpleNamespace(
        db_path="fixture:database", github_token="REDACTED_CREDENTIAL",
        limits=SimpleNamespace(max_repos=None, max_cases=None, max_seconds=None),
        config=config or {},
    )


QUERY_CONSTANTS = (
    "LOOKBACK_START_DATE", "TARGETED_ISSUE_LINK_TERMS",
    "TARGETED_STREAMS", "SINGLE_STREAM_HIGH_SIGNAL_TERMS",
)
TARGETED_NAMES = (
    "_targeted_base_query", "_targeted_queries_for_term",
    "_interleave_by_stream", "_term_allowed_for_language",
    "_targeted_query_jobs", "_record_case_retrieval", "_pipeline_event",
    "_case_ids_for_pr", "_known_pr_outcomes", "_repo_visible_outcome_count",
    "_repo_full_name_from_url", "_limit_reached", "_collect_targeted_stream_search",
)


def _literal_original_constants(names):
    """Lift only immutable literal assignments from the SHA-checked source AST."""
    raw = SOURCE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COLLECTOR_SHA256:
        raise ValueError("Historical source hash mismatch before constant extraction")
    tree = ast.parse(raw)
    found = {}
    for node in tree.body:
        name = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if name in names:
            found[name] = ast.literal_eval(node.value)
    if set(found) != set(names):
        raise ValueError(f"Missing literal original constants: {set(names) - set(found)}")
    return found


class TargetedReplayClock:
    """Capture original sleep calls without actually waiting."""

    def __init__(self):
        self.sleeps = []

    @staticmethod
    def time():
        return 1000.0

    def sleep(self, seconds):
        self.sleeps.append(float(seconds))


def load_original_targeted_search():
    """Extract the historical resumable targeted collector; enforce disposable IO."""
    clock = TargetedReplayClock()
    scope = _extract(TARGETED_NAMES, {
        **_literal_original_constants(QUERY_CONSTANTS),
        "math": math, "time": clock,
        "log": logging.getLogger("arno.archived_targeted_contract"),
        "Database": Database, "GitHubClient": FixtureSearchOnly,
        "GitHubAPIError": GitHubAPIError,
        "GitHubSecondaryRateLimit": type("GitHubSecondaryRateLimit", (RuntimeError,), {}),
        "_process_pr": load_original_process_pr(),
    })
    original = scope["_collect_targeted_stream_search"]

    def checked_targeted(*, db, gh, settings, start=1000.0, initial_case_count=0):
        if not isinstance(gh, FixtureSearchOnly):
            raise TypeError("FixtureSearchOnly is required; no live GitHub API permitted")
        if not isinstance(db, Database) or db.read_only or db.command_spool is not None:
            raise TypeError("A disposable original Database is required")
        path = Path(db.path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if (not path.is_relative_to(temp_root) or path.name != "miner.sqlite"
                or not path.parent.name.startswith("arno_disposable_original_db_")
                or not path.is_file()):
            raise ValueError("Refusing collector outside disposable DB harness")
        return original(db, gh, settings, start, initial_case_count=initial_case_count)

    scope["run"] = checked_targeted
    scope["clock"] = clock
    return scope
