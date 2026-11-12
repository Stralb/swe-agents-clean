"""Test-only: connect the exact archived collect() to its real targeted handler.

Never import the historical collector module, initialize its GitHubClient,
open a caller-specified SQLite path or invoke unreviewed retrieval modes.
Both source functions are loaded via checksum-checked AST allowlists.
"""
from __future__ import annotations

import logging
import posixpath
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.db.database import Database
from src.github.replay_client import ReplayGitHubClient
from tests.support.archived_collection_contract import (
    FixtureSearchOnly,
    IncompleteReplayError,
    _extract,
    load_original_targeted_search,
)

DB_SENTINEL = "fixture:database"
TOKEN_SENTINEL = "NON_SECRET_FIXTURE_TOKEN"


def _require_disposable(db: Database) -> None:
    """Reject paths outside the existing disposable_original_database() harness."""
    if not isinstance(db, Database) or db.read_only or db.command_spool is not None:
        raise TypeError("A writable disposable original Database is required")
    path = Path(db.path).resolve()
    root = Path(tempfile.gettempdir()).resolve()
    if (not path.is_relative_to(root) or path.name != "miner.sqlite"
            or not path.parent.name.startswith("arno_disposable_original_db_")
            or not path.is_file()):
        raise ValueError("Only the existing disposable database harness is permitted")


class ConnectedTargetedDispatch:
    """Bind original dispatch and targeted functions without production services.

    The object carries a *single* in-memory API fixture transport and a fresh
    disposable database. All other collection handlers abort, never silently
    returning made-up case counts. A run is synchronous; no hidden background work.
    """

    def __init__(self, db: Database, gh: FixtureSearchOnly):
        _require_disposable(db)
        if not isinstance(gh, FixtureSearchOnly) or not isinstance(gh._client, ReplayGitHubClient):
            raise TypeError("FixtureSearchOnly with ReplayGitHubClient is required")
        self.db = db
        self.gh = gh
        self.targeted = load_original_targeted_search()
        self.dispatch_calls: list[str] = []
        self.client_kwargs: dict[str, Any] = {}
        self._clock = SimpleNamespace(time=lambda: 1000.0)
        self._fake_os = SimpleNamespace(
            environ={},
            path=SimpleNamespace(join=posixpath.join),
        )
        self._scope = _extract(("collect",), {
            "Database": self._database,
            "GitHubClient": self._github,
            "time": self._clock,
            "os": self._fake_os,
            "log": logging.getLogger("arno.connected_targeted_dispatch"),
            "_limit_reached": self._unavailable_limit,
            "_collect_targeted_stream_search": self._targeted,
            "_collect_repo_month_pr_search": self._unavailable("repo_month"),
            "_collect_ai_search": self._unavailable("ai_search"),
            "_collect_repo_walk": self._unavailable("repo_walk"),
        })
        self._original_collect = self._scope["collect"]

    def _database(self, path: str):
        _require_disposable(self.db)
        if path != DB_SENTINEL:
            raise ValueError("Dispatcher may not open caller-provided SQLite paths")
        self.dispatch_calls.append("database_ctor")
        return self.db

    def _github(self, token: str, **kwargs: Any):
        if token != TOKEN_SENTINEL:
            raise ValueError("Only synthetic token sentinel is accepted")
        self.dispatch_calls.append("github_ctor")
        self.client_kwargs = dict(kwargs)
        return self.gh

    def _targeted(self, db, gh, settings, start, initial_case_count=0):
        if db is not self.db or gh is not self.gh:
            raise TypeError("A different database or GitHub client was supplied")
        self.dispatch_calls.append("targeted")
        return self.targeted["run"](
            db=db, gh=gh, settings=settings, start=start,
            initial_case_count=initial_case_count,
        )

    def _unavailable(self, name: str):
        def reject(*args, **kwargs):
            self.dispatch_calls.append(name)
            raise IncompleteReplayError(
                f"Historical {name} collection handler is not fixture-connected; "
                "refusing to pretend this mode ran"
            )
        return reject

    @staticmethod
    def _unavailable_limit(*args, **kwargs):
        raise IncompleteReplayError("Hybrid-mode original budget decisions are not fixture-connected")

    def run(self, settings) -> None:
        """Run exact archived collect() *only* for its targeted retrieval branch."""
        _require_disposable(self.db)
        if getattr(settings, "db_path", None) != DB_SENTINEL:
            raise ValueError("Settings must use the non-path disposable DB sentinel")
        if getattr(settings, "github_token", None) != TOKEN_SENTINEL:
            raise ValueError("Settings must use the synthetic token sentinel")
        cfg = getattr(settings, "config", None)
        if not isinstance(cfg, dict):
            raise TypeError("Test settings must supply a config dict")
        # Validate mode prior to constructors so unsupported modes cannot write
        # even when the archived dispatcher would select another handler.
        mode = str((cfg.get("collection") or {}).get("retrieval_mode", "targeted")).lower()
        if mode not in {"targeted", "streams", "stream", "targeted_pr_search", "wide", "wide_first"}:
            raise IncompleteReplayError("Only historical targeted retrieval modes are connected")
        return self._original_collect(settings)
