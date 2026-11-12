"""Synthetic tests of historical-style lookback and repository-universe gates.

No GitHub, Wits, file-backed database, scanner, or archived script execution.
"""
from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

from src.db.ephemeral import open_ephemeral_database
from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from src.pipeline.collector_gates import (
    SECONDS_PER_HISTORICAL_MONTH,
    lookback_start_datetime,
    positive_lookback_months,
    repo_passes_universe,
    require_explicit_lookback_clock,
    within_lookback,
)
from src.pipeline.offline_case_collection import FixtureCollectionPolicy, collect_fixture_pr


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 21, 8, 0, tzinfo=timezone.utc)
START = "2026-10-01T00:00:00Z"


class PureGateContractTests(unittest.TestCase):
    def test_positive_months_match_original_config_fallback(self):
        self.assertEqual(positive_lookback_months("2"), 2)
        for bad in (None, "bad", "0", "-1", ""):
            self.assertIsNone(positive_lookback_months(bad))

    def test_configured_start_treats_naive_as_utc(self):
        start = lookback_start_datetime("2026-10-01")
        self.assertEqual(start.isoformat(), "2026-10-01T00:00:00+00:00")
        self.assertEqual(lookback_start_datetime("2026-10-01T02:00:00+02:00").timestamp(), start.timestamp())
        self.assertIsNone(lookback_start_datetime("garbage"))

    def test_start_cutoff_is_inclusive(self):
        start = lookback_start_datetime(START)
        self.assertTrue(within_lookback("2026-10-01T00:00:00Z", start=start))
        self.assertFalse(within_lookback("2026-09-30T23:59:59Z", start=start))

    def test_configured_start_precedes_months(self):
        start = lookback_start_datetime(START)
        self.assertFalse(within_lookback("2026-09-01T00:00:00Z", months=120, start=start))
        self.assertTrue(within_lookback("2026-10-02T00:00:00Z", months=1, start=start))

    def test_historical_relative_month_is_31_days(self):
        self.assertEqual(SECONDS_PER_HISTORICAL_MONTH, 31 * 86400)
        cutoff = NOW - timedelta(days=31)
        self.assertTrue(within_lookback(cutoff.isoformat(), months=1, reference_now_utc=NOW))
        self.assertFalse(within_lookback((cutoff - timedelta(seconds=1)).isoformat(), months=1, reference_now_utc=NOW))

    def test_missing_or_bad_event_timestamp_passes_like_original(self):
        for item in (None, "", "not-a-timestamp"):
            self.assertTrue(within_lookback(item, start=lookback_start_datetime(START)))
            self.assertTrue(within_lookback(item, months=1, reference_now_utc=NOW))

    def test_explicit_clock_required_only_for_relative_months(self):
        with self.assertRaisesRegex(ValueError, "reference_now_utc"):
            require_explicit_lookback_clock(1, None, reference_now_utc=None)
        with self.assertRaisesRegex(ValueError, "timezone"):
            require_explicit_lookback_clock(1, None, reference_now_utc=datetime(2026,10,21))
        require_explicit_lookback_clock(1, lookback_start_datetime(START), reference_now_utc=None)
        require_explicit_lookback_clock(None, None, reference_now_utc=None)

    def test_naive_issue_datetime_is_refused_when_comparison_needed(self):
        # Historical uses the machine's local zone for datetime.timestamp().
        with self.assertRaisesRegex(ValueError, "Naive"):
            within_lookback("2026-10-10T00:00:00", start=lookback_start_datetime(START))
        self.assertTrue(within_lookback("2026-10-10T00:00:00"))

    def test_original_repository_filter_priority_and_reason(self):
        repo = {"stargazers_count": 250, "has_issues": True}
        self.assertEqual(repo_passes_universe(repo), (True, "ok"))
        self.assertEqual(repo_passes_universe({**repo, "archived": True, "fork": True}),
                         (False, "repo_filter:archived"))
        self.assertEqual(repo_passes_universe({**repo, "fork": True}),
                         (False, "repo_filter:fork"))
        self.assertEqual(repo_passes_universe({**repo, "stargazers_count": 50, "has_issues": False}),
                         (False, "repo_filter:stars_below_200"))
        self.assertEqual(repo_passes_universe({**repo, "has_issues": False}),
                         (False, "repo_filter:issues_disabled"))
        self.assertEqual(repo_passes_universe({**repo, "stargazers_count": 50}, configured_min_stars=0),
                         (False, "repo_filter:stars_below_200"))

    def test_recovered_original_definitions_are_preserved(self):
        # Static AST inspection only: no importing or executing original collector.
        text = (ROOT / "historical/miner/2026-10-20-live-export/src/pipeline/collect_pipeline.py").read_text()
        tree = ast.parse(text)
        defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.assertTrue({
            "_lookback_months", "_lookback_start", "_iso_dt",
            "_within_lookback", "_repo_passes_universe", "_process_pr",
        }.issubset(defs))
        self.assertIn("months * 31 * 24 * 60 * 60", text)
        self.assertIn('return False, "repo_filter:archived"', text)


class OfflineCollectorLookbackTests(unittest.TestCase):
    def setUp(self):
        self.db = open_ephemeral_database()
        self.addCleanup(self.db.close)
        self.tape = FixtureTransport()
        self.client = ReplayGitHubClient(self.tape)
        self.repo = {"full_name": "example/repo", "html_url": "https://example.invalid/repo",
                     "stargazers_count": 900}
        self.pr = {
            "number": 12, "html_url": "https://example.invalid/pr/12",
            "title": "Fixes #8", "body": "Fixes #8", "merged_at": "2026-10-10T12:00:00Z",
            "head": {"ref": "codex/task"}, "user": {"login": "alice"}
        }
        self.issue = {
            "number": 8, "html_url": "https://example.invalid/issues/8",
            "title": "Fix regression", "body": "Fix the TypeScript regression with a real patch.",
            "created_at": "2026-10-02T10:00:00Z",
        }
        self.policy = FixtureCollectionPolicy(
            lookback_start=START,
            require_javascript_typescript_surface=True,
            require_issue_quality_filter=True,
            min_issue_words=3,
        )

    def count(self, table: str) -> int:
        return self.db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]

    def add_pr(self, **changes):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, **changes})

    def add_pr_files(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12/files",
                      params={"per_page": 100, "page": 1},
                      data=[{"filename": "src/fix.ts", "status": "modified"}])

    def add_issue(self, **changes):
        self.tape.add("GET", "/repos/example/repo/issues/8", data={**self.issue, **changes})

    def collect(self, policy=None):
        return collect_fixture_pr(self.db,self.client,self.repo,12,
                                  policy=self.policy if policy is None else policy)

    def test_old_pr_fails_before_files_fetch(self):
        self.add_pr(merged_at="2026-09-30T23:59:00Z")
        out = self.collect()
        self.assertEqual(out.reason, "outside_lookback_pr")
        self.assertEqual(self.count("cases"), 0)
        self.assertEqual(len(self.tape.calls), 1)

    def test_repo_screen_fails_before_api_request(self):
        self.repo["archived"] = True
        out = self.collect(replace(self.policy, enforce_repo_universe=True))
        self.assertEqual(out.reason, "repo_filter:archived")
        self.assertEqual(len(self.tape.calls), 0)
        self.assertEqual(self.count("excluded_cases"), 1)

    def test_low_stars_can_be_excluded_before_requests(self):
        self.repo["stargazers_count"] = 50
        out = self.collect(replace(self.policy, enforce_repo_universe=True))
        self.assertEqual(out.reason, "repo_filter:stars_below_200")
        self.assertEqual(len(self.tape.calls), 0)

    def test_issue_too_old_rejected_after_fetch(self):
        self.add_pr()
        self.add_pr_files()
        self.add_issue(created_at="2026-09-01T10:00:00Z")
        out = self.collect()
        self.assertEqual(out.reason, "outside_lookback_issue")
        self.assertEqual(self.count("cases"), 0)
        self.assertEqual(self.count("excluded_cases"), 1)
        self.assertEqual(len(self.tape.calls), 3)

    def test_recent_issue_and_pr_are_persisted(self):
        self.add_pr()
        self.add_pr_files()
        self.add_issue()
        out = self.collect()
        self.assertTrue(out.accepted)
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.count("issue_pr_links"), 1)

    def test_issue_updated_date_fallback_when_configured(self):
        self.add_pr()
        self.add_pr_files()
        self.add_issue(created_at="2026-09-01T10:00:00Z",
                       updated_at="2026-10-03T10:00:00Z")
        out = self.collect(replace(self.policy, require_issue_created_after_lookback=False))
        self.assertTrue(out.accepted)

    def test_pr_updated_date_fallback_when_configured(self):
        self.add_pr(merged_at=None, updated_at="2026-10-11T10:00:00Z", closed_at=None)
        self.add_pr_files()
        self.add_issue()
        out = self.collect(replace(self.policy,
                                   require_pr_merged_after_lookback=False,
                                   include_closed_unmerged_prs=True))
        self.assertTrue(out.accepted)

    def test_missing_pr_merge_time_passes_lookback_but_unmerged_fails(self):
        self.add_pr(merged_at=None)
        out = self.collect()
        self.assertEqual(out.reason, "unmerged_pr")
        self.assertEqual(len(self.tape.calls), 1)

    def test_missing_issue_timestamp_passes_original_rule(self):
        self.add_pr()
        self.add_pr_files()
        self.add_issue(created_at=None)
        self.assertTrue(self.collect().accepted)

    def test_relative_months_require_explicit_clock_prior_to_fixture_access(self):
        with self.assertRaisesRegex(ValueError, "reference_now_utc"):
            self.collect(replace(self.policy, lookback_start=None, lookback_months=1))
        self.assertEqual(self.count("excluded_cases"), 0)
        self.assertEqual(len(self.tape.calls), 0)

    def test_relative_month_filter_controls_pr(self):
        self.add_pr(merged_at="2026-08-01T00:00:00Z")
        out = self.collect(replace(self.policy,lookback_start=None,
                                   lookback_months=1,reference_now_utc=NOW))
        self.assertEqual(out.reason, "outside_lookback_pr")

    def test_start_precedence_allows_missing_clock(self):
        self.add_pr()
        self.add_pr_files()
        self.add_issue()
        out = self.collect(replace(self.policy,lookback_months=1,reference_now_utc=None))
        self.assertTrue(out.accepted)

    def test_invalid_start_falls_back_to_no_constraint(self):
        self.add_pr(merged_at="2026-08-01T00:00:00Z")
        self.add_pr_files()
        self.add_issue(created_at="2026-07-01T00:00:00Z")
        out = self.collect(replace(self.policy, lookback_start="invalid"))
        self.assertTrue(out.accepted)

    def test_naive_pr_date_cannot_be_silently_assumed_utc(self):
        self.add_pr(merged_at="2026-10-10T12:00:00")
        with self.assertRaisesRegex(ValueError, "Naive"):
            self.collect()
        self.assertEqual(self.count("excluded_cases"), 0)

    def test_no_lookup_screen_when_opt_in_disabled(self):
        self.repo["stargazers_count"] = 0
        self.add_pr()
        self.add_pr_files()
        self.add_issue()
        self.assertTrue(self.collect().accepted)
