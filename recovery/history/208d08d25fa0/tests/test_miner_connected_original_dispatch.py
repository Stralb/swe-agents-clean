"""Exact original collect() -> original targeted handler -> original _process_pr.

Fixture transport and disposable original database ONLY; no live APIs or Wits
files. Non-targeted historical modes deliberately fail closed.
"""
from __future__ import annotations

from types import SimpleNamespace
import socket
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from src.db.database import Database
from src.db.disposable_harness import disposable_original_database
from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from tests.support.archived_collection_contract import (
    FixtureSearchOnly, IncompleteReplayError, fixture_settings,
)
from tests.support.connected_original_dispatch import ConnectedTargetedDispatch


class ConnectedHistoricalCollectorTests(unittest.TestCase):
    def setUp(self):
        self.context = disposable_original_database()
        self.db = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.tape = FixtureTransport()
        self.gh = FixtureSearchOnly(ReplayGitHubClient(self.tape))
        self.runner = ConnectedTargetedDispatch(self.db, self.gh)
        self.cfg = {
            "github": {"language": "TypeScript", "min_stars": 200,
                       "strict_primary_language": True},
            "retrieval": {"query_phases": ["issue_link_baseline"]},
            "collection": {
                "retrieval_mode": "targeted",
                "targeted_per_page": 2,
                "targeted_max_pages": 1,
                "targeted_max_pages_total": 3,
                "targeted_max_terms": 1,
                "targeted_pause_seconds": 0,
                "lookback_start": "2025-01-01",
                "require_javascript_typescript_surface": True,
                "require_issue_quality_filter": True,
                "require_primary_worker": False,
                "require_high_yield_surface": False,
                "fetch_pr_comments_for_issue_links": False,
                "fetch_commit_messages_for_issue_links": False,
                "fetch_commit_messages_for_ai": False,
                "max_linked_issues_per_pr_for_evidence": 1,
                "ai_only": True,
            },
            "filters": {
                "min_issue_words": 3, "issue_min_body_chars": 0,
                "english_only": False, "exclude_bots": [],
                "exclude_non_behaviour_only": True,
                "exclude_docs_scope_only": True,
            },
            "ai_markers": {
                "high_confidence": ["codex/"], "medium_confidence": [],
            },
        }
        self.settings = fixture_settings(self.cfg)
        self.settings.limits = SimpleNamespace(
            max_repos=None, max_prs=None, max_cases=None,
            max_cases_per_repo=None, max_seconds=None,
        )

    def query(self):
        return self.runner.targeted["_targeted_query_jobs"](self.settings)[0][2]

    def search_page(self, data, page=1, *, status=200, body=""):
        self.tape.add(
            "GET", "/search/issues",
            params={"q": self.query(), "sort": "updated", "order": "desc",
                    "per_page": 2, "page": page},
            data={"items": data}, status_code=status, body=body,
        )

    def record_case(self):
        self.search_page([{
            "number": 12,
            "pull_request": {"url": "https://api.github.com/repos/example/repo/pulls/12"},
            "repository_url": "https://api.github.com/repos/example/repo",
        }])
        self.tape.add("GET", "/repos/example/repo", data={
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
            "stargazers_count": 900,
            "language": "TypeScript",
            "archived": False,
        })
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={
            "number": 12,
            "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8", "body": "Fixes #8\nRepair build system",
            "state": "closed", "merged_at": "2026-10-10T12:00:00Z",
            "head": {"ref": "codex/repair", "sha": "abc"},
            "base": {"ref": "main", "sha": "def"},
            "user": {"login": "alice"},
            "additions": 4, "changed_files": 1,
        })
        self.tape.add(
            "GET", "/repos/example/repo/pulls/12/files",
            params={"per_page": 100, "page": 1},
            data=[{"filename": "src/runner.ts", "status": "modified", "additions": 4}],
        )
        self.tape.add("GET", "/repos/example/repo/issues/8", data={
            "number": 8, "id": 8008,
            "html_url": "https://example.invalid/example/repo/issues/8",
            "title": "Build failure",
            "body": "Please fix the failing build in src/runner.ts, rather than changing docs.",
            "state": "open", "created_at": "2026-10-01T00:00:00Z",
            "user": {"login": "bob"}, "labels": [],
        })

    def count(self, table):
        approved = {
            "cases", "repos", "issues", "pull_requests", "pr_files",
            "issue_pr_links", "upstream_features", "ai_markers",
            "retrieval_queries", "case_retrievals",
        }
        if table not in approved:
            raise ValueError("No arbitrary table names in test SQL")
        return self.db.one(f"SELECT COUNT(*) AS n FROM {table}")["n"]

    def test_original_dispatch_runs_original_handler_and_creates_case(self):
        self.record_case()
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            with mock.patch("time.sleep", side_effect=AssertionError("real delay")):
                self.assertIsNone(self.runner.run(self.settings))
        self.assertEqual(self.runner.dispatch_calls, ["database_ctor", "github_ctor", "targeted"])
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.count("repos"), 1)
        self.assertEqual(self.count("issues"), 1)
        self.assertEqual(self.count("pull_requests"), 1)
        self.assertEqual(self.count("pr_files"), 1)
        self.assertEqual(self.count("issue_pr_links"), 1)
        self.assertEqual(self.count("upstream_features"), 1)
        self.assertEqual(self.count("ai_markers"), 1)
        self.assertEqual(self.count("retrieval_queries"), 1)
        self.assertEqual(self.count("case_retrievals"), 1)
        self.assertEqual(self.db.one("SELECT status FROM cases")["status"], "metadata_collected")
        self.assertEqual(
            self.db.one("SELECT final_query FROM case_retrievals")["final_query"], self.query(),
        )

    def test_second_dispatch_reuses_exhausted_cursor(self):
        self.record_case()
        self.runner.run(self.settings)
        count = len(self.tape.calls)
        self.assertIsNone(self.runner.run(self.settings))
        self.assertEqual(len(self.tape.calls), count)
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.count("ai_markers"), 1)
        self.assertEqual(self.count("case_retrievals"), 1)
        self.assertEqual(self.runner.dispatch_calls.count("targeted"), 2)

    def test_non_targeted_handler_is_not_simulated(self):
        self.cfg["collection"]["retrieval_mode"] = "repo_month"
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(self.runner.dispatch_calls, [])
        self.assertEqual(self.count("retrieval_queries"), 0)
        self.assertEqual(self.count("cases"), 0)

    def test_ai_only_and_hybrid_branches_refuse_unconnected_handlers(self):
        for mode in ("ai_only", "repo_universe", "downstream_first", "repo_walk"):
            with self.subTest(mode=mode):
                self.cfg["collection"]["retrieval_mode"] = mode
                with self.assertRaises(IncompleteReplayError):
                    self.runner.run(self.settings)
                self.assertEqual(self.count("cases"), 0)

    def test_targeted_alias_invokes_historical_targeted_handler(self):
        for mode in ("streams", "stream", "targeted_pr_search", "wide", "wide_first"):
            with self.subTest(mode=mode):
                self.cfg["collection"]["retrieval_mode"] = mode
                self.search_page([])
                self.runner.run(self.settings)
                self.assertEqual(self.runner.dispatch_calls[-1], "targeted")
                self.assertEqual(self.count("cases"), 0)
                # The first run exhausts the query; subsequent aliases reuse it.

    def test_missing_fixture_fails_closed(self):
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(self.count("cases"), 0)

    def test_search_error_propagates_in_original_state_machine(self):
        self.search_page([], status=500, body="temporary failure")
        self.assertIsNone(self.runner.run(self.settings))
        row = self.db.one("SELECT next_page, status FROM retrieval_queries")
        self.assertEqual((row["next_page"], row["status"]), (1, "error"))
        self.assertEqual(self.count("cases"), 0)

    def test_real_database_path_refused_even_when_disposable_object_exists(self):
        self.settings.db_path = str(self.db.path)
        with self.assertRaises(ValueError):
            self.runner.run(self.settings)
        self.assertEqual(self.runner.dispatch_calls, [])

    def test_real_token_refused_before_client_constructor(self):
        self.settings.github_token = "REDACTED_CREDENTIAL"
        with self.assertRaises(ValueError):
            self.runner.run(self.settings)
        self.assertEqual(self.runner.dispatch_calls, [])

    def test_non_disposable_database_rejected(self):
        with tempfile.TemporaryDirectory(prefix="not_an_arno_db_") as directory:
            suspect = Database(Path(directory) / "miner.sqlite", read_only=False)
            with self.assertRaises(ValueError):
                ConnectedTargetedDispatch(suspect, self.gh)

    def test_non_fixture_client_rejected(self):
        with self.assertRaises(TypeError):
            ConnectedTargetedDispatch(self.db, object())

    def test_constructor_options_stay_in_memory(self):
        self.search_page([])
        self.runner.run(self.settings)
        self.assertIn("cache_enabled", self.runner.client_kwargs)
        self.assertIn("search_min_remaining", self.runner.client_kwargs)
        self.assertNotIn("token", self.runner.client_kwargs)
        self.assertEqual(self.db.one("SELECT COUNT(*) AS n FROM cases")["n"], 0)
