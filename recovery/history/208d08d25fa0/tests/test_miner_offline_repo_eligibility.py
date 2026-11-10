"""Deterministic original-style JS/TS repository eligibility against memory SQLite."""
from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
import sqlite3
import unittest

from src.db.ephemeral import open_ephemeral_database
from src.github.replay_client import FixtureTransport, MissingFixtureError, ReplayGitHubClient
from src.pipeline.offline_case_collection import FixtureCollectionPolicy, collect_fixture_pr
from src.pipeline.offline_repo_eligibility import evaluate_fixture_repo_eligibility

ROOT = Path(__file__).resolve().parents[1]


class EligibilityDBTests(unittest.TestCase):
    def setUp(self):
        self.db = open_ephemeral_database()
        self.addCleanup(self.db.close)
        self.tape = FixtureTransport()
        self.gh = ReplayGitHubClient(self.tape)
        self.repo = {
            "full_name": "example/repo", "stargazers_count": 300,
            "language": "TypeScript", "archived": False, "fork": False,
            "has_issues": True, "html_url": "https://example.invalid/repo",
        }
        self.lang = {"JavaScript": 400, "TypeScript": 100, "Python": 500}

    def languages(self, value=None):
        self.tape.add("GET", "/repos/example/repo/languages",
                      data=self.lang if value is None else value)

    def evaluate(self, **kwargs):
        return evaluate_fixture_repo_eligibility(
            self.db, self.gh, "example/repo", repo_metadata=self.repo, **kwargs)

    def count(self):
        return self.db.execute("SELECT count(*) FROM repo_eligibility").fetchone()[0]

    def test_eligible_at_exact_share_boundary(self):
        self.languages()
        result = self.evaluate()
        self.assertTrue(result["eligible"])
        self.assertEqual(result["reason"], "eligible")
        self.assertEqual(result["js_ts_bytes"], 500)
        self.assertEqual(result["total_language_bytes"], 1000)
        self.assertEqual(result["js_ts_share"], 0.5)
        self.assertFalse(result["cached"])
        self.assertEqual(self.count(), 1)

    def test_share_below_threshold_formatted_original_reason(self):
        self.languages({"TypeScript": 499, "Python": 501})
        self.assertEqual(self.evaluate()["reason"], "js_ts_share_below_0.5000")
        self.assertEqual(self.count(), 1)

    def test_missing_language_bytes(self):
        self.languages({})
        res = self.evaluate()
        self.assertEqual(res["reason"], "no_language_bytes")
        self.assertEqual(res["total_language_bytes"], 0)

    def test_negative_language_byte_entries_are_ignored(self):
        self.languages({"TypeScript": 60, "Python": 40, "Deleted": -50})
        result = self.evaluate()
        self.assertEqual(result["total_language_bytes"], 100)
        self.assertNotIn("Deleted", result["language_bytes"])
        self.assertTrue(result["eligible"])

    def test_historical_category_priority_archived_over_fork(self):
        self.repo.update({"archived": True, "fork": True})
        self.languages()
        self.assertEqual(self.evaluate()["reason"], "archived")

    def test_fork_priority_over_issue_disabled(self):
        self.repo.update({"fork": True, "has_issues": False})
        self.languages()
        self.assertEqual(self.evaluate()["reason"], "fork")

    def test_disabled_issue_priority_over_stars(self):
        self.repo.update({"has_issues": False, "stargazers_count": 1})
        self.languages()
        self.assertEqual(self.evaluate()["reason"], "issues_disabled")

    def test_stars_below_configured_minimum(self):
        self.repo["stargazers_count"] = 90
        self.languages()
        self.assertEqual(self.evaluate()["reason"], "stars_below_100")

    def test_case_sensitive_language_names_as_source(self):
        self.languages({"typescript": 900, "Python": 100})
        self.assertEqual(self.evaluate()["reason"], "js_ts_share_below_0.5000")

    def test_cached_result_avoids_extra_github_fixtures(self):
        self.languages()
        first = self.evaluate()
        second = self.evaluate()
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(len(self.tape.calls), 1)
        self.assertEqual(self.count(), 1)

    def test_force_refresh_replaces_cache_row(self):
        self.languages()
        self.evaluate()
        self.languages({"TypeScript": 1, "Python": 999})
        fresh = self.evaluate(force_refresh=True)
        self.assertFalse(fresh["cached"])
        self.assertFalse(fresh["eligible"])
        self.assertEqual(self.count(), 1)

    def test_changed_threshold_invalidates_cached_decision(self):
        self.languages()
        self.evaluate()
        self.languages()
        second = self.evaluate(min_js_ts_share=0.7)
        self.assertFalse(second["cached"])
        self.assertEqual(second["reason"], "js_ts_share_below_0.7000")
        self.assertEqual(self.count(), 1)
        self.assertEqual(len(self.tape.calls), 2)

    def test_changed_threshold_tiny_difference_within_cache_tolerance(self):
        self.languages()
        self.evaluate()
        # Exact historical cache query uses abs(delta) < 0.0000001
        second = self.evaluate(min_js_ts_share=0.50000001)
        self.assertTrue(second["cached"])
        self.assertEqual(len(self.tape.calls), 1)

    def test_repository_metadata_fetched_if_not_supplied(self):
        self.tape.add("GET", "/repos/example/repo", data=self.repo)
        self.languages()
        result = evaluate_fixture_repo_eligibility(self.db,self.gh,"example/repo")
        self.assertTrue(result["eligible"])
        self.assertEqual(len(self.tape.calls), 2)

    def test_empty_metadata_triggers_repo_get_like_historical_code(self):
        self.tape.add("GET", "/repos/example/repo", data=self.repo)
        self.languages()
        result = evaluate_fixture_repo_eligibility(self.db,self.gh,"example/repo",repo_metadata={})
        self.assertTrue(result["eligible"])

    def test_missing_language_fixture_does_not_write(self):
        with self.assertRaises(MissingFixtureError):
            self.evaluate()
        self.assertEqual(self.count(), 0)

    def test_bad_language_payload_fails_no_row(self):
        self.languages(["not", "a", "mapping"])
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.count(), 0)

    def test_language_value_conversion_error_fails_before_write(self):
        self.languages({"TypeScript": "not bytes"})
        with self.assertRaises(ValueError):
            self.evaluate()
        self.assertEqual(self.count(), 0)

    def test_bad_repository_name_rejected_without_requests(self):
        with self.assertRaises(ValueError):
            evaluate_fixture_repo_eligibility(self.db,self.gh,"../repo")
        self.assertEqual(len(self.tape.calls),0)

    def test_file_or_attached_database_is_refused(self):
        self.db.execute("ATTACH DATABASE ':memory:' AS attached")
        with self.assertRaisesRegex(ValueError, "attached"):
            self.evaluate()
        self.db.execute("DETACH DATABASE attached")

    def test_sqlite_trigger_failure_rolls_back_eligibility_row(self):
        self.db.execute("""CREATE TRIGGER reject_repo BEFORE INSERT ON repo_eligibility
                     BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
        self.languages()
        with self.assertRaises(sqlite3.IntegrityError):
            self.evaluate()
        self.assertEqual(self.count(), 0)

    def test_original_historical_module_present_only_under_archive(self):
        path = ROOT / "historical/miner/2026-10-20-live-export/src/pipeline/repo_eligibility.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defs = {node.name for node in tree.body if isinstance(node,ast.FunctionDef)}
        self.assertTrue({"ensure_repo_eligibility_schema","evaluate_repo_eligibility"}.issubset(defs))
        self.assertFalse((ROOT/"src/pipeline/repo_eligibility.py").exists())


class IntegrationWithOfflineCollectorTests(unittest.TestCase):
    def setUp(self):
        self.db=open_ephemeral_database()
        self.addCleanup(self.db.close)
        self.tape=FixtureTransport()
        self.gh=ReplayGitHubClient(self.tape)
        self.repo={
            "full_name":"example/repo", "html_url":"https://example.invalid/repo",
            "stargazers_count":300, "language":"TypeScript",
        }
        self.pr={
            "number":12, "html_url":"https://example.invalid/pull/12", "title":"Fixes #8",
            "body":"Fixes #8", "merged_at":"2026-10-20T10:00:00Z",
            "head":{"ref":"codex/repair"}, "user":{"login":"alice"},
        }
        self.issue={
            "number":8, "html_url":"https://example.invalid/issues/8",
            "title":"Bug", "body":"Fix this issue with typed code please.",
            "created_at":"2026-10-18T11:00:00Z",
        }
        self.policy=FixtureCollectionPolicy(
            require_repo_js_ts_share=True,
            repo_eligibility_min_stars=100,
            repo_eligibility_min_js_ts_share=0.5,
            require_javascript_typescript_surface=True,
        )

    def enqueue_case(self):
        self.tape.add("GET","/repos/example/repo/pulls/12",data=self.pr)
        self.tape.add("GET","/repos/example/repo/pulls/12/files",
                      params={"per_page":100,"page":1},data=[{"filename":"src/patch.ts"}])
        self.tape.add("GET","/repos/example/repo/issues/8",data=self.issue)

    def enroll(self,lang):
        self.tape.add("GET","/repos/example/repo/languages",data=lang)

    def collect(self):
        return collect_fixture_pr(self.db,self.gh,self.repo,12,policy=self.policy)

    def count(self,table):
        return self.db.execute("SELECT count(*) FROM "+table).fetchone()[0]

    def test_eligible_repository_then_case_persists(self):
        self.enroll({"TypeScript":550,"Python":450})
        self.enqueue_case()
        out=self.collect()
        self.assertTrue(out.accepted)
        self.assertEqual(self.count("repo_eligibility"),1)
        self.assertEqual(self.count("cases"),1)
        self.assertEqual([c.path for c in self.tape.calls][:1],["/repos/example/repo/languages"])

    def test_failed_eligibility_rejects_before_pr_api(self):
        self.enroll({"TypeScript":200,"Python":800})
        out=self.collect()
        self.assertEqual(out.reason,"repo_eligibility:js_ts_share_below_0.5000")
        self.assertEqual(self.count("repo_eligibility"),1)
        self.assertEqual(self.count("excluded_cases"),1)
        self.assertEqual(self.count("cases"),0)
        self.assertEqual(len(self.tape.calls),1)

    def test_cache_reused_across_repeated_pr_replays(self):
        self.enroll({"TypeScript":800,"Python":200})
        self.enqueue_case()
        first=self.collect()
        self.enqueue_case()
        second=self.collect()
        self.assertEqual(first.case_ids,second.case_ids)
        self.assertEqual(self.count("repo_eligibility"),1)
        self.assertEqual(self.count("cases"),1)
        self.assertEqual(len([x for x in self.tape.calls if x.path.endswith("/languages")]),1)

    def test_missing_languages_aborts_before_case_or_exclusion_write(self):
        with self.assertRaises(MissingFixtureError):
            self.collect()
        self.assertEqual(self.count("repo_eligibility"),0)
        self.assertEqual(self.count("cases"),0)
        self.assertEqual(self.count("excluded_cases"),0)

    def test_opt_in_disabled_does_not_fetch_language_metadata(self):
        self.enqueue_case()
        out=collect_fixture_pr(self.db,self.gh,self.repo,12,
                               policy=replace(self.policy,require_repo_js_ts_share=False))
        self.assertTrue(out.accepted)
        self.assertEqual(self.count("repo_eligibility"),0)
