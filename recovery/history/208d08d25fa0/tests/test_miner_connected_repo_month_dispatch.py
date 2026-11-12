"""Original repo-month dispatcher + core pulls + _process_pr in disposable SQLite.

This does not import/run the historical collector module or read historical
seed databases. Repository seeds and every GitHub response are synthetic.
"""
from __future__ import annotations

from types import SimpleNamespace
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from src.db.database import Database
from src.db.disposable_harness import disposable_original_database
from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from tests.support.archived_collection_contract import IncompleteReplayError, fixture_settings
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_fixture_scan_case import ArchivedFixtureScanCase, FixtureScannerProviders
from tests.support.connected_repo_month_dispatch import (
    ConnectedRepoMonthDispatch, FixtureStructuralGitHub,
)


class ConnectedHistoricalRepoMonthTests(unittest.TestCase):
    def setUp(self):
        context = disposable_original_database()
        self.db = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.tape = FixtureTransport()
        self.gh = FixtureStructuralGitHub(ReplayGitHubClient(self.tape))
        self.runner = ConnectedRepoMonthDispatch(
            self.db, self.gh, seed_names=("example/repo",),
        )
        self.config = {
            "github": {"language": "TypeScript", "min_stars": 200},
            "collection": {
                "retrieval_mode": "repo_month",
                "repo_selection_lane": "exploit",
                "active_repo_seed": False,
                "use_graphql_hydration": False,
                "require_graphql_same_repo_link": False,
                "lookback_start": "2026-10-01",
                "lookback_months": 1,
                "repo_month_per_page": 2,
                "repo_month_max_pages": 1,
                "repo_sample_strategy": "random",
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
        self.settings = fixture_settings(self.config)
        self.settings.limits = SimpleNamespace(
            max_repos=2, max_prs=None, max_cases=None,
            max_cases_per_repo=None, max_seconds=None,
        )

    def rows(self, table):
        allowed = {"repos", "cases", "issue_pr_links", "retrieval_queries", "ai_markers",
                   "pr_files", "case_retrievals", "issues", "excluded_cases"}
        if table not in allowed:
            raise ValueError("Only fixture tables are allowed")
        return self.db.query(f"SELECT * FROM {table}")

    def repo(self, *, stars=900, archived=False):
        self.tape.add("GET", "/repos/example/repo", data={
            "full_name": "example/repo",
            "html_url": "https://example.invalid/example/repo",
            "stargazers_count": stars,
            "language": "TypeScript",
            "archived": archived, "fork": False, "has_issues": True,
        })

    def pr(self, *, merged="2026-10-10T12:00:00Z", draft=False):
        return {
            "number": 12,
            "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8", "body": "Fixes #8\nRepair build system",
            "state": "closed", "merged_at": merged, "draft": draft,
            "head": {"ref": "codex/repair", "sha": "abc"},
            "base": {"ref": "main", "sha": "def"},
            "user": {"login": "alice"}, "additions": 4, "changed_files": 1,
        }

    def closed_pulls(self, entries=None):
        self.tape.add(
            "GET", "/repos/example/repo/pulls",
            params={"state": "closed", "sort": "updated",
                    "direction": "desc", "per_page": 50, "page": 1},
            data=entries if entries is not None else [self.pr()],
        )

    def full_case(self):
        self.repo()
        self.closed_pulls()
        self.tape.add("GET", "/repos/example/repo/pulls/12", data=self.pr())
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

    def test_exact_repo_month_path_creates_case_with_original_schema(self):
        self.full_case()
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            self.assertIsNone(self.runner.run(self.settings))
        self.assertEqual(self.rows("cases")[0]["status"], "metadata_collected")
        self.assertEqual(len(self.rows("cases")), 1)
        self.assertEqual(len(self.rows("issue_pr_links")), 1)
        self.assertEqual(len(self.rows("pr_files")), 1)
        self.assertEqual(len(self.rows("ai_markers")), 1)
        retrievals = self.rows("case_retrievals")
        self.assertEqual(len(retrievals), 1)
        self.assertEqual(retrievals[0]["stream_key"], "repo_month")
        self.assertIn("core-pulls:example/repo:2026-10-01..2026-11-01",
                      retrievals[0]["final_query"])
        self.assertIn("repo_month", self.runner.calls)
        self.assertIn("fixture_repo_seed", self.runner.calls)
        self.assertEqual(len(self.rows("retrieval_queries")), 2)  # seeded + month

    def test_original_one_repo_cap_stops_before_first_month(self):
        """Historical max_repos=1 interacts with a nested repo-count check."""
        self.settings.limits.max_repos = 1
        self.full_case()
        self.assertIsNone(self.runner.run(self.settings))
        self.assertEqual(len(self.rows("cases")), 0)
        self.assertEqual(
            [row["stream_key"] for row in self.rows("retrieval_queries")],
            ["existing_repo_seed"],
        )
        # The repository is fetched and counted, but no closed-PR API request
        # runs because _limit_reached(1, max_repos=1) gates the month loop.
        self.assertEqual(
            [(call.method, call.path) for call in self.tape.calls],
            [("GET", "/repos/example/repo")],
        )

    def test_original_collection_worker_scanner_and_case_status_handoff(self):
        """One synthetic case crosses exact archived collector, queue, and scanner stages."""
        self.full_case()
        self.runner.run(self.settings)
        case = self.db.one("SELECT id, pr_id FROM cases")
        self.assertIsNotNone(case)
        queue = load_original_queue(self.db)
        self.assertEqual(queue["seed_scanner_jobs"](self.db), 6)
        self.assertEqual(self.db.one(
            "SELECT status FROM cases WHERE id=?", (case["id"],)
        )["status"], "scanner_running")

        backends = FixtureScannerProviders(gitleaks=[
            ([{"description": "SYNTHETIC token exposure",
               "severity": "HIGH", "introduced": True, "rule": "fixture-secret"}],
             {"status": "ok", "stdout": "synthetic scan", "stderr": ""}),
        ])
        scan = ArchivedFixtureScanCase(self.db, backends)
        with mock.patch("socket.create_connection", side_effect=AssertionError("network")):
            with mock.patch("subprocess.run", side_effect=AssertionError("scanner binary")):
                scan.run({
                    "case_id": case["id"], "pr_id": case["pr_id"],
                    "repo_url": "https://example.invalid/example/repo",
                    "base_sha": "def", "head_sha": "abc",
                }, {
                    "scanners": {
                        "gitleaks": True, "dependency_downgrade": False,
                        "osv": False, "trivy": False, "semgrep": False, "codeql": False,
                    },
                    "cache": {"force_rescan": False},
                })
        queue["sync_jobs_from_scanner_runs"](self.db, case["id"])
        queue["update_case_stages"](self.db)
        job = self.db.one(
            "SELECT status FROM scanner_jobs WHERE case_id=? AND job_type='secret_ci'",
            (case["id"],),
        )
        self.assertEqual(job["status"], "ok")
        finding = self.db.one(
            "SELECT finding_type,scanner,introduced FROM scanner_findings WHERE case_id=?",
            (case["id"],),
        )
        self.assertEqual((finding["finding_type"],finding["scanner"],finding["introduced"]),
                         ("secret","gitleaks",1))
        self.assertEqual(self.db.one(
            "SELECT status,downstream_signal FROM cases WHERE id=?", (case["id"],)
        )["status"], "needs_review")
        self.assertEqual(backends.calls, [("gitleaks", 1)])

    def test_repo_window_alias_uses_original_full_window_handler(self):
        self.config["collection"]["retrieval_mode"] = "downstream_first"
        self.full_case()
        self.runner.run(self.settings)
        retrieval = self.rows("case_retrievals")[0]
        self.assertEqual(retrieval["stream_key"], "repo_window")
        self.assertEqual(len(self.rows("cases")), 1)

    def test_repo_excluded_by_stars_before_core_pr_call(self):
        self.repo(stars=2)
        self.runner.run(self.settings)
        self.assertEqual(len(self.rows("cases")), 0)
        self.assertEqual(len(self.rows("excluded_cases")), 1)
        self.assertEqual(self.rows("excluded_cases")[0]["reason"], "repo_filter")
        self.assertEqual(len(self.tape.calls), 1)

    def test_draft_and_unmerged_closed_pulls_do_not_hydrate(self):
        self.repo()
        self.closed_pulls([
            self.pr(merged=None),
            self.pr(draft=True),
            self.pr(merged="2026-12-01T12:00:00Z"),
        ])
        self.runner.run(self.settings)
        self.assertEqual(len(self.rows("cases")), 0)
        rows = [x for x in self.rows("retrieval_queries") if x["stream_key"] == "repo_month"]
        self.assertEqual(rows[0]["raw_count"], 0)

    def test_missing_seed_repo_response_fails_closed(self):
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(len(self.rows("cases")), 0)

    def test_missing_core_pull_page_fails_closed(self):
        self.repo()
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(len(self.rows("cases")), 0)

    def test_explore_lane_is_explicitly_unavailable(self):
        self.config["collection"]["repo_selection_lane"] = "explore"
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(self.runner.calls, [])

    def test_graphql_hydration_must_be_disabled(self):
        self.config["collection"]["use_graphql_hydration"] = True
        with self.assertRaises(IncompleteReplayError):
            self.runner.run(self.settings)
        self.assertEqual(self.runner.calls, [])

    def test_real_seed_path_cannot_be_loaded(self):
        self.runner.fake_environ["MINING_REPO_SEED_DB"] = "/home/wits/private.db"
        with self.assertRaises(ValueError):
            self.runner.run(self.settings)
        self.assertEqual(len(self.rows("cases")), 0)

    def test_credential_and_database_path_are_refused(self):
        self.settings.github_token = "REDACTED_CREDENTIAL"
        with self.assertRaises(ValueError):
            self.runner.run(self.settings)
        self.settings.github_token = "REDACTED_CREDENTIAL"
        self.settings.db_path = str(self.db.path)
        with self.assertRaises(ValueError):
            self.runner.run(self.settings)

    def test_external_database_disallowed(self):
        with tempfile.TemporaryDirectory(prefix="unrelated_sqlite_") as path:
            fake_db = Database(Path(path) / "miner.sqlite", read_only=False)
            with self.assertRaises(ValueError):
                ConnectedRepoMonthDispatch(fake_db, self.gh, seed_names=("example/repo",))

    def test_incorrect_github_client_rejected(self):
        with self.assertRaises(TypeError):
            ConnectedRepoMonthDispatch(self.db, object(), seed_names=("example/repo",))
