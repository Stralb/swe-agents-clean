"""Exact archived repo-window/repo-month *exploit lane*, executed in fixtures only.

The original runtime seeded this lane from MINING_REPO_SEED_DB. Here that
variable is always a non-file sentinel, and its loader is replaced by a
hardcoded seed list supplied by the test. No Wits/research DB is accessed.
Every actual collector function comes from the checksum-checked original AST.
"""
from __future__ import annotations

import json
import logging
import posixpath
import random
from types import SimpleNamespace

from src.db.database import Database
from src.filters.bot_filter import is_excluded_bot
from src.github.replay_client import MissingFixtureError, ReplayGitHubClient, GitHubAPIError
from src.pipeline.repo_universe import (
    global_active_pr_query, lookback_window, month_windows, shard_accept,
    star_band_queries,
)
from tests.support.archived_collection_contract import (
    FixtureSearchOnly, IncompleteReplayError, _extract, _literal_original_constants,
)
from tests.support.archived_pr_contract import load_original_process_pr
from tests.support.connected_original_dispatch import (
    DB_SENTINEL, TOKEN_SENTINEL, _require_disposable,
)

SEED_SENTINEL = "fixture:repo_seed"
REPO_MONTH_FUNCTIONS = (
    "_record_case_retrieval", "_pipeline_event", "_case_ids_for_pr",
    "_known_pr_outcomes", "_repo_visible_outcome_count",
    "_sample_strategy", "_random_seed", "_pool_multiplier",
    "_stable_shuffle", "_limit_reached", "_repo_full_name_from_url",
    "_graphql_hydrate_pr", "_same_repo_graphql_issue_links",
    "_bot_author_terms", "_github_languages", "_repo_passes_universe",
    "_process_structural_pr_search", "_collect_repo_month_pr_search",
)
ALLOWED_REPO_MODES = frozenset({
    "repo_month", "repo_month_pr_search", "repo_window",
    "repo_window_pr_search", "repo_window_adaptive",
    "repo_universe", "downstream_first",
})


class FixtureStructuralGitHub(FixtureSearchOnly):
    """Add explicit offline-only core PR listing and repository search methods."""

    def __init__(self, client: ReplayGitHubClient):
        super().__init__(client)

    def closed_pulls(self, *args, **kwargs):
        try:
            yield from self._client.closed_pulls(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc

    def search_repos(self, *args, **kwargs):
        try:
            yield from self._client.search_repos(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc

    def graphql(self, *args, **kwargs):
        try:
            return self._client.graphql(*args, **kwargs)
        except MissingFixtureError as exc:
            raise IncompleteReplayError(str(exc)) from exc


class ConnectedRepoMonthDispatch:
    """Join original collect() to original repo-month and structural PR handlers.

    Only the 'exploit' lane with explicit synthetic seed names is permitted;
    live seed DB reading, exploration search and GraphQL are refused.
    """

    def __init__(self, db: Database, gh: FixtureStructuralGitHub, *, seed_names: tuple[str, ...]):
        _require_disposable(db)
        if not isinstance(gh, FixtureStructuralGitHub):
            raise TypeError("FixtureStructuralGitHub must be supplied explicitly")
        if not isinstance(seed_names, tuple) or not seed_names or not all(
            isinstance(x, str) and x.count("/") == 1 and not x.startswith("/")
            for x in seed_names
        ):
            raise ValueError("Provide at least one explicit synthetic owner/repo seed")
        self.db = db
        self.gh = gh
        self.seed_names = seed_names
        self.calls: list[str] = []
        self.fake_environ = {
            "MINING_REPO_SEED_DB": SEED_SENTINEL,
            "MINING_REPO_SELECTION_LANE": "exploit",
        }
        self.fake_os = SimpleNamespace(
            environ=self.fake_environ,
            path=SimpleNamespace(join=posixpath.join),
        )
        self.clock = SimpleNamespace(time=lambda: 1000.0)
        original_scope = _extract(REPO_MONTH_FUNCTIONS, {
            **_literal_original_constants(("LOOKBACK_START_DATE",)),
            "json": json, "random": random,
            "time": self.clock, "os": self.fake_os,
            "log": logging.getLogger("arno.archived_repo_month_fixture"),
            "GitHubClient": FixtureStructuralGitHub,
            "Database": Database,
            "GitHubAPIError": GitHubAPIError,
            "GitHubSecondaryRateLimit": type("GitHubSecondaryRateLimit", (RuntimeError,), {}),
            "is_excluded_bot": is_excluded_bot,
            "month_windows": month_windows, "lookback_window": lookback_window,
            "shard_accept": shard_accept,
            "global_active_pr_query": global_active_pr_query,
            "star_band_queries": star_band_queries,
            "_process_pr": load_original_process_pr(),
            "load_existing_repo_seed_names": self._seed_names,
            "PR_HYDRATION_QUERY": "fixture:graphql-query-blocked",
        })
        self.original_handler = original_scope["_collect_repo_month_pr_search"]
        self.scope = _extract(("collect",), {
            "Database": self._database,
            "GitHubClient": self._github,
            "os": self.fake_os,
            "time": self.clock,
            "log": logging.getLogger("arno.archived_repo_month_dispatch"),
            "_limit_reached": self._unavailable_limit,
            "_collect_repo_month_pr_search": self._repo_month,
            "_collect_targeted_stream_search": self._unavailable("targeted"),
            "_collect_ai_search": self._unavailable("ai_search"),
            "_collect_repo_walk": self._unavailable("repo_walk"),
        })

    def _database(self, path):
        _require_disposable(self.db)
        if path != DB_SENTINEL:
            raise ValueError("Only a non-file database sentinel is allowed")
        self.calls.append("database_ctor")
        return self.db

    def _github(self, token, **kwargs):
        if token != TOKEN_SENTINEL:
            raise ValueError("Live credentials are forbidden")
        self.calls.append("github_ctor")
        return self.gh

    def _seed_names(self, path):
        if path != SEED_SENTINEL:
            raise ValueError("Historical seed database paths are prohibited")
        self.calls.append("fixture_repo_seed")
        return list(self.seed_names)

    def _repo_month(self, db, gh, settings, start, initial_case_count=0):
        if db is not self.db or gh is not self.gh:
            raise TypeError("Injected services unexpectedly changed")
        self.calls.append("repo_month")
        return self.original_handler(db, gh, settings, start, initial_case_count)

    def _unavailable(self, name):
        def reject(*args, **kwargs):
            raise IncompleteReplayError(f"Historical {name} mode not fixture-connected")
        return reject

    @staticmethod
    def _unavailable_limit(*args, **kwargs):
        raise IncompleteReplayError("Other collection modes cannot use stub budgets")

    def run(self, settings):
        _require_disposable(self.db)
        if getattr(settings, "db_path", None) != DB_SENTINEL:
            raise ValueError("Refusing caller-provided database path")
        if getattr(settings, "github_token", None) != TOKEN_SENTINEL:
            raise ValueError("Refusing non-fixture GitHub credentials")
        cfg = getattr(settings, "config", None)
        if not isinstance(cfg, dict):
            raise TypeError("Config dictionary required")
        collection = cfg.get("collection") or {}
        if not isinstance(collection, dict):
            raise TypeError("Collection configuration must be a dict")
        mode = str(collection.get("retrieval_mode") or "").lower()
        if mode not in ALLOWED_REPO_MODES:
            raise IncompleteReplayError("Only original repo-window/month dispatch is connected")
        if collection.get("use_graphql_hydration", True) is not False:
            raise IncompleteReplayError("GraphQL hydration must be explicitly disabled")
        if collection.get("require_graphql_same_repo_link", False):
            raise IncompleteReplayError("GraphQL same-repo requirement cannot be skipped")
        if collection.get("repo_selection_lane", "exploit") != "exploit":
            raise IncompleteReplayError("Only fixture-seeded exploit lane is connected")
        if collection.get("active_repo_seed", False) is not False:
            raise IncompleteReplayError("Live structural seeding must be disabled")
        # Original repo handler imports datetime itself; its month arithmetic
        # uses real calendar months. Tests choose a fixed one-month window, not
        # the full current/historical corpus.
        return self.scope["collect"](settings)
