"""Full synthetic PR->issue->case path through original schema; memory only."""
from __future__ import annotations

import sqlite3
import unittest
from dataclasses import replace
from unittest import mock

from src.db.ephemeral import open_ephemeral_database
from src.github.replay_client import FixtureTransport, MissingFixtureError, ReplayGitHubClient, GitHubAPIError
from src.pipeline.offline_case_collection import (
    FixtureCollectionPolicy, FixtureCollectionOutcome, collect_fixture_pr,
)


class OfflineCaseCollectionTests(unittest.TestCase):
    def setUp(self):
        self.db = open_ephemeral_database()
        self.addCleanup(self.db.close)
        self.tape = FixtureTransport()
        self.github = ReplayGitHubClient(self.tape)
        self.repo = {
            "full_name": "example/repo", "html_url": "https://example.invalid/example/repo",
            "stargazers_count": 900, "language": "TypeScript",
        }
        self.pr = {
            "number": 12, "html_url": "https://example.invalid/example/repo/pull/12",
            "title": "Fixes #8", "body": "Resolve build failure linked to #8",
            "state": "closed", "merged_at": "2026-10-10T12:00:00Z",
            "head": {"ref": "codex/repair", "sha": "abcd"},
            "base": {"ref": "main", "sha": "defg"},
            "user": {"login": "alice"}, "additions": 4, "changed_files": 1,
        }
        self.issue = {
            "number": 8, "id": 1208,
            "html_url": "https://example.invalid/example/repo/issues/8",
            "title": "Unexpected regression", "body": "Build test fails after update. Please repair src/runner.ts.",
            "state": "closed", "labels": [{"name": "bug"}], "comments": 2,
            "user": {"login": "bob"}, "created_at": "2026-10-01T10:00:00Z",
        }
        self.files = [{"filename": "src/runner.ts", "status": "modified", "additions": 4, "deletions": 1}]
        self.policy = FixtureCollectionPolicy(
            ai_only=True,
            ai_marker_config={"ai_markers": {"high_confidence": ["codex/"], "medium_confidence": []}},
            require_javascript_typescript_surface=True,
            require_issue_quality_filter=True,
            min_issue_words=3,
        )

    def enqueue(self, *, pr=None, files=None, issue=None, issue_status=200, files_status=200,
                request_issue_number=8, extra_issues=()):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data=self.pr if pr is None else pr)
        if (self.pr if pr is None else pr).get("merged_at") is not None:
            self.tape.add("GET", "/repos/example/repo/pulls/12/files",
                          params={"per_page": 100, "page": 1},
                          status_code=files_status, body="unavailable" if files_status >= 400 else "",
                          data=self.files if files is None else files)
        if request_issue_number:
            self.tape.add("GET", f"/repos/example/repo/issues/{request_issue_number}",
                          data=self.issue if issue is None else issue,
                          status_code=issue_status,
                          body="not found" if issue_status == 404 else "server error" if issue_status >= 400 else "")
        for number, data in extra_issues:
            self.tape.add("GET", f"/repos/example/repo/issues/{number}", data=data)

    def run_case(self, policy=None):
        return collect_fixture_pr(self.db, self.github, self.repo, 12,
                                  policy=self.policy if policy is None else policy)

    def count(self, table):
        return self.db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def test_accepts_and_persists_pr_issue_case_features_and_marker(self):
        self.enqueue()
        result = self.run_case()
        self.assertEqual(result.reason, "metadata_collected")
        self.assertEqual(result.issue_numbers, (8,))
        self.assertEqual(len(result.case_ids), 1)
        for table in ["repos", "pull_requests", "issues", "pr_files", "issue_pr_links",
                      "cases", "upstream_features", "ai_markers"]:
            with self.subTest(table=table):
                self.assertEqual(self.count(table), 1)
        case = self.db.execute("SELECT status,ai_cohort,auto_tags FROM cases").fetchone()
        self.assertEqual(case["status"], "metadata_collected")
        self.assertEqual(case["ai_cohort"], "AI-explicit-high")
        self.assertEqual(case["auto_tags"], '["AI-explicit-high"]')
        self.assertEqual(self.db.execute("SELECT method FROM issue_pr_links").fetchone()[0], "closing-keyword")
        self.assertEqual(self.db.execute("SELECT category FROM pr_files").fetchone()[0], "source")
        self.assertEqual(self.db.execute("SELECT is_english FROM issues").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT has_ai_marker FROM upstream_features").fetchone()[0], 1)
        self.assertEqual(self.count("scanner_jobs"), 0)
        self.assertEqual(self.count("excluded_cases"), 0)
        self.assertEqual(len(self.tape.calls), 3)

    def test_replay_is_idempotent_for_cases_and_markers(self):
        self.enqueue()
        first = self.run_case()
        self.enqueue()
        second = self.run_case()
        self.assertEqual(first.case_ids, second.case_ids)
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.count("pr_files"), 1)
        self.assertEqual(self.count("ai_markers"), 1)

    def test_missing_pr_fixture_fails_before_any_db_mutation(self):
        with self.assertRaises(MissingFixtureError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)
        self.assertEqual(self.count("excluded_cases"), 0)

    def test_missing_issue_fixture_is_not_swallowed(self):
        self.enqueue(request_issue_number=0)
        with self.assertRaises(MissingFixtureError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)
        self.assertEqual(self.count("excluded_cases"), 0)

    def test_missing_issue_404_is_recorded_as_exclusion(self):
        self.enqueue(issue_status=404)
        result = self.run_case()
        self.assertEqual(result.reason, "stale_or_missing_issue_reference")
        self.assertEqual(self.count("repos"), 0)
        self.assertEqual(self.db.execute("SELECT reason FROM excluded_cases").fetchone()[0], result.reason)

    def test_unexpected_issue_500_propagates_without_writes(self):
        self.enqueue(issue_status=500)
        with self.assertRaises(GitHubAPIError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)
        self.assertEqual(self.count("excluded_cases"), 0)

    def test_pr_files_422_is_not_mistaken_for_valid_case(self):
        self.enqueue(files_status=422)
        result = self.run_case()
        self.assertEqual(result.reason, "pr_files_unavailable")
        self.assertEqual(self.count("cases"), 0)
        self.assertEqual(self.count("excluded_cases"), 1)

    def test_docs_only_pr_excluded(self):
        self.enqueue(files=[{"filename": "README.md"}])
        result = self.run_case(replace(self.policy, require_javascript_typescript_surface=False))
        self.assertEqual(result.reason, "non_behaviour_only")
        self.assertEqual(self.count("cases"), 0)

    def test_docs_scope_python_config_excluded(self):
        self.enqueue(files=[{"filename": "docs/conf.py"}])
        result = self.run_case(replace(self.policy, require_javascript_typescript_surface=False))
        self.assertEqual(result.reason, "docs_only_change")

    def test_js_ts_surface_requirement(self):
        self.enqueue(files=[{"filename": "src/module.py"}])
        self.assertEqual(self.run_case().reason, "no_javascript_typescript_surface")

    def test_no_issue_link_reason(self):
        self.enqueue(pr={**self.pr, "title": "Update build", "body": "No issue reference", "head": {"ref": "codex/update"}}, request_issue_number=0)
        self.assertEqual(self.run_case().reason, "no_linked_issue")

    def test_bot_filter_runs_before_files_fetch(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, "user": {"login": "renovate[bot]"}})
        result = self.run_case(replace(self.policy, exclude_bots=("renovate",)))
        self.assertEqual(result.reason, "bot_maintenance")
        self.assertEqual(len(self.tape.calls), 1)

    def test_unmerged_rejected_before_files(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, "merged_at": None})
        self.assertEqual(self.run_case().reason, "unmerged_pr")
        self.assertEqual(len(self.tape.calls), 1)

    def test_case_quality_word_gate(self):
        self.enqueue(issue={**self.issue, "body": "short"})
        self.assertEqual(self.run_case().reason, "issue_filter")
        self.assertEqual(self.count("cases"), 0)

    def test_empty_ai_markers_when_ai_only(self):
        self.enqueue()
        result = self.run_case(replace(self.policy, ai_marker_config={"ai_markers": {}}))
        self.assertEqual(result.reason, "ai_marker_required")

    def test_ai_unknown_can_still_be_collected(self):
        self.enqueue()
        result = self.run_case(replace(self.policy, ai_only=False, ai_marker_config={}))
        self.assertTrue(result.accepted)
        self.assertEqual(self.count("ai_markers"), 0)
        self.assertEqual(self.db.execute("SELECT ai_cohort FROM cases").fetchone()[0], "AI-unknown")

    def test_linked_item_is_pr_excluded(self):
        self.enqueue(issue={**self.issue, "pull_request": {}})
        self.assertEqual(self.run_case().reason, "linked_item_is_pr")

    def test_max_scope_excluded(self):
        self.enqueue(files=[{"filename": "src/x.ts"}, {"filename": "src/y.ts"}])
        self.assertEqual(self.run_case(replace(self.policy, max_changed_files_for_evidence=1)).reason,
                         "pr_scope_too_large_for_evidence")

    def test_multi_issue_default_excluded_without_issue_fetch(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, "title": "Fixes #8 and closes #9"})
        self.tape.add("GET", "/repos/example/repo/pulls/12/files",
                      params={"per_page": 100, "page": 1}, data=self.files)
        self.assertEqual(self.run_case().reason, "ambiguous_multi_issue_pr")
        self.assertEqual(len(self.tape.calls), 2)

    def test_issue_identity_mismatch_refused_without_writes(self):
        self.enqueue(issue={**self.issue, "number": 19})
        with self.assertRaises(ValueError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)

    def test_pr_identity_mismatch_refused_without_writes(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, "number": 55})
        with self.assertRaises(ValueError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)

    def test_injection_failure_rolls_back_entire_transaction(self):
        self.db.execute("CREATE TRIGGER reject_issue BEFORE INSERT ON issues BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END;")
        self.enqueue()
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_case()
        self.assertEqual(self.count("repos"), 0)
        self.assertEqual(self.count("pull_requests"), 0)
        self.assertEqual(self.count("pr_files"), 0)
        self.assertEqual(self.count("cases"), 0)

    def test_memory_only_guard_rejects_attached_db_even_in_memory(self):
        self.db.execute("ATTACH DATABASE ':memory:' AS other")
        self.enqueue()
        with self.assertRaisesRegex(ValueError, "attached"):
            self.run_case()
        self.assertEqual(len(self.tape.calls), 0)
        self.db.execute("DETACH DATABASE other")

    def test_requires_explicit_policy_and_fixture_client(self):
        with self.assertRaises(TypeError):
            collect_fixture_pr(self.db, object(), self.repo, 12, policy=self.policy)
        with self.assertRaises(TypeError):
            collect_fixture_pr(self.db, self.github, self.repo, 12, policy=None)

    def test_rejects_unexpected_repo_name(self):
        with self.assertRaises(ValueError):
            collect_fixture_pr(self.db, self.github, {"full_name": "../danger", "html_url": "https://example.invalid"}, 12, policy=self.policy)
        self.assertEqual(len(self.tape.calls), 0)

    def test_two_links_one_missing_keeps_valid_case_and_exclusion(self):
        self.tape.add("GET", "/repos/example/repo/pulls/12", data={**self.pr, "title": "Fixes #8 and closes #9"})
        self.tape.add("GET", "/repos/example/repo/pulls/12/files",
                      params={"per_page": 100, "page": 1}, data=self.files)
        self.tape.add("GET", "/repos/example/repo/issues/8", data=self.issue)
        self.tape.add("GET", "/repos/example/repo/issues/9", status_code=404, body="not found")
        result = self.run_case(replace(self.policy, max_linked_issues_per_pr_for_evidence=2))
        self.assertTrue(result.accepted)
        self.assertEqual(result.issue_numbers, (8,))
        self.assertEqual(result.excluded_reasons, ("stale_or_missing_issue_reference",))
        self.assertEqual(self.count("cases"), 1)
        self.assertEqual(self.count("excluded_cases"), 1)

    def test_english_gate_fallback_is_explicitly_pinned(self):
        chinese = "漢字" * 80
        issue = {**self.issue, "title": chinese, "body": chinese}
        self.enqueue(issue=issue)
        with mock.patch("src.utils.text.detect_langs", None):
            result = self.run_case(replace(self.policy, english_only=True, min_issue_words=0))
        self.assertEqual(result.reason, "issue_filter")
        self.assertEqual(self.count("cases"), 0)

    def test_issues_cannot_violate_original_foreign_keys(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO issues(repo_id,number,url) VALUES(?,?,?)", (777, 1, "https://example.invalid/x"))


if __name__ == "__main__":
    unittest.main()
