"""Load an exact, SHA-verified historical PR handler for OFFLINE contract tests.

This is a deliberately narrow AST extraction of function definitions, NOT an
import of the 3,000-line miner collector and NOT a production mining entrypoint.
Only the frozen October 2026 source is accepted. Call it with a fixture-only
GitHub client and a newly created disposable_original_database().

The handler retains historical side effects within the supplied test database.
It can insert partial PR rows before an issue fails, and can duplicate markers
on replay. It is NOT transactional and must never receive a Wits DB path.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from functools import wraps
import tempfile
from types import SimpleNamespace
from typing import Any
import time

from src.db.database import Database
from src.filters.bot_filter import is_excluded_bot
from src.filters.issue_filters import passes_issue_filters
from src.filters.pr_filters import (
    enrich_files, classify_pr_files, is_docs_scope_only,
    has_javascript_typescript_surface,
)
from src.filters.tool_applicability import (
    has_any_applicable_downstream_worker, has_high_yield_downstream_surface,
    has_primary_applicable_downstream_worker, route_reasons,
)
from src.github.issue_linker import find_linked_issue_numbers
from src.github.replay_client import GitHubAPIError, MissingFixtureError, ReplayGitHubClient
from src.markers.ai_markers import detect_ai_markers
from src.markers.upstream_features import extract_upstream_features

ORIGINAL_COLLECTOR_SHA256 = "5c907fff25c2a0e5f9db5a068e266f47ff6126512924ac401e37ab888f87b750"
SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py"
)
EXTRACTED_NAMES = (
    "_process_pr", "_safe_commit_messages", "_store_upstream_features",
    "_lookback_months", "_lookback_start", "_iso_dt", "_within_lookback",
    "_lookback_description", "_min_issue_body_chars", "_issue_body_char_count",
)


class IncompleteReplayError(BaseException):
    """Testing-only fail-closed abort, including if original catches Exception."""


class FixtureOnlyGitHub:
    """Wrap replay transport; never let the historical handler hide missing fixtures.

    The archived handler catches broad Exception at a few API boundaries. This
    wrapper uses a BaseException subclass for fixture gaps so tests cannot
    incorrectly interpret an incomplete replay as a deliberate exclusion.
    """

    def __init__(self, client: ReplayGitHubClient):
        if not isinstance(client, ReplayGitHubClient):
            raise TypeError("ReplayGitHubClient is required; live GitHub is prohibited")
        self._client = client

    def get(self, *args: Any, **kwargs: Any) -> Any:
        try:
            return self._client.get(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc

    def paginate(self, *args: Any, **kwargs: Any) -> Any:
        try:
            yield from self._client.paginate(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc


def load_original_process_pr():
    """Compile only an exact allowlist of frozen AST function definitions.

    No original top-level imports, module-body expressions, script entrypoints,
    helpers outside the allowlist, or original collect() are executed.
    """
    data = SOURCE_PATH.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != ORIGINAL_COLLECTOR_SHA256:
        raise ValueError(f"Historical collector source hash mismatch: {digest}")
    tree = ast.parse(data, filename=str(SOURCE_PATH))
    selected = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in EXTRACTED_NAMES}
    if set(selected) != set(EXTRACTED_NAMES):
        raise ValueError(f"Missing historical function(s): {set(EXTRACTED_NAMES) - set(selected)}")
    # Ensure decorated original functions are not implicitly invoking code.
    if any(n.decorator_list for n in selected.values()):
        raise ValueError("Decorated historical functions are not approved for extraction")
    extracted = ast.fix_missing_locations(ast.Module(
        body=[selected[n] for n in EXTRACTED_NAMES], type_ignores=[]
    ))
    scope = {
        "__builtins__": __builtins__,
        "__name__": "_offline_archived_pr_contract",
        "log": logging.getLogger("arno.archived_pr_contract"),
        "time": time, "datetime": datetime, "timezone": timezone,
        "Any": Any, "Settings": SimpleNamespace, "Database": Database,
        "GitHubClient": FixtureOnlyGitHub, "GitHubAPIError": GitHubAPIError,
        "GitHubSecondaryRateLimit": type("GitHubSecondaryRateLimit", (RuntimeError,), {}),
        "enrich_files": enrich_files, "classify_pr_files": classify_pr_files,
        "is_docs_scope_only": is_docs_scope_only,
        "has_javascript_typescript_surface": has_javascript_typescript_surface,
        "has_any_applicable_downstream_worker": has_any_applicable_downstream_worker,
        "has_primary_applicable_downstream_worker": has_primary_applicable_downstream_worker,
        "has_high_yield_downstream_surface": has_high_yield_downstream_surface,
        "route_reasons": route_reasons,
        "is_excluded_bot": is_excluded_bot,
        "passes_issue_filters": passes_issue_filters,
        "find_linked_issue_numbers": find_linked_issue_numbers,
        "detect_ai_markers": detect_ai_markers,
        "extract_upstream_features": extract_upstream_features,
    }
    compiled = compile(extracted, str(SOURCE_PATH), "exec", flags=__future__.annotations.compiler_flag, dont_inherit=True)
    exec(compiled, scope, scope)
    original = scope["_process_pr"]

    @wraps(original)
    def checked_process(**kwargs):
        db = kwargs.get("db")
        gh = kwargs.get("gh")
        if not isinstance(gh, FixtureOnlyGitHub):
            raise TypeError("An explicitly fixture-only GitHub client is required")
        if not isinstance(db, Database) or db.read_only or db.command_spool is not None:
            raise TypeError("An initialized, writable disposable Database is required")
        path = Path(db.path).resolve()
        temp_root = Path(tempfile.gettempdir()).resolve()
        if (not path.is_relative_to(temp_root) or path.name != "miner.sqlite"
                or not path.parent.name.startswith("arno_disposable_original_db_")
                or not path.is_file()):
            raise ValueError("Refusing original PR handler outside disposable harness")
        return original(**kwargs)

    return checked_process
