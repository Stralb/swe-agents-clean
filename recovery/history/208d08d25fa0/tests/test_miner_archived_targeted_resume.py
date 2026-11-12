"""Exact archived targeted search/resume exercised on fresh SQLite + API fixtures.

All changes occur only within the disposable_original_database() test context.
The historic miner, existing databases, real GitHub and cluster are untouched.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest import mock

from src.db.database import Database
from src.db.disposable_harness import disposable_original_database
from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from tests.support.archived_collection_contract import (
    FixtureSearchOnly, load_original_targeted_search,
)
from tests.support.archived_pr_contract import IncompleteReplayError


class ArchivedTargetedCollectionTests(unittest.TestCase):
    def setUp(self):
        self.context = disposable_original_database()
        self.db = self.context.__enter__()
        self.addCleanup(self.context.__exit__, None, None, None)
        self.tape = FixtureTransport()
        self.gh = FixtureSearchOnly(ReplayGitHubClient(self.tape))
        self.original = load_original_targeted_search()
        self.config = {
            'github': {'language': 'TypeScript', 'min_stars': 200,
                       'strict_primary_language': True},
            'retrieval': {'query_phases': ['issue_link_baseline']},
            'collection': {
                'targeted_per_page': 2, 'targeted_max_pages': 1,
                'targeted_max_pages_total': 3, 'targeted_max_terms': 1,
                'targeted_pause_seconds': 1,
                'lookback_start': '2025-01-01',
                'require_javascript_typescript_surface': True,
                'require_issue_quality_filter': True,
                'require_primary_worker': False,
                'require_high_yield_surface': False,
                'fetch_pr_comments_for_issue_links': False,
                'fetch_commit_messages_for_issue_links': False,
                'fetch_commit_messages_for_ai': False,
                'max_linked_issues_per_pr_for_evidence': 1,
                'ai_only': True,
            },
            'filters': {
                'min_issue_words': 3, 'issue_min_body_chars': 0,
                'english_only': False, 'exclude_bots': [],
                'exclude_non_behaviour_only': True,
                'exclude_docs_scope_only': True,
            },
            'ai_markers': {'high_confidence': ['codex/'], 'medium_confidence': []},
        }
        self.limits = SimpleNamespace(max_repos=None, max_prs=None, max_cases=None,
                                      max_cases_per_repo=None, max_seconds=None)
        self.settings = SimpleNamespace(config=self.config, limits=self.limits)

    def jobs(self):
        return self.original['_targeted_query_jobs'](self.settings)[:self.config['collection']['targeted_max_terms']]

    def register_results(self, page, items, *, query=None, status=200, error=''):
        q = self.jobs()[0][2] if query is None else query
        self.tape.add('GET', '/search/issues', params={
            'q': q, 'sort': 'updated', 'order': 'desc', 'per_page': 2, 'page': page,
        }, data={'items': items}, status_code=status, body=error)

    def run_original(self):
        return self.original['run'](db=self.db, gh=self.gh, settings=self.settings)

    def row(self, query=None):
        q = self.jobs()[0][2] if query is None else query
        return self.db.one('SELECT * FROM retrieval_queries WHERE final_query=?', (q,))

    def test_uses_original_query_builder_and_known_job_order(self):
        q = self.jobs()[0][2]
        self.assertEqual(q,
            'is:pr is:merged language:TypeScript stars:>=200 archived:false '
            'merged:>=2025-01-01 in:title,body "fixes #"')
        self.assertEqual(self.jobs()[0][:2], ('issue_links', '"fixes #"'))
        self.assertEqual(self.original['_targeted_query_jobs'](self.settings)[1][1], '"closes #"')

    def test_resume_after_full_page_then_exhaust_after_short_page(self):
        self.register_results(1, [{'number': 1}, {'number': 2}])
        self.assertEqual(self.run_original(), 0)
        first = self.row()
        self.assertEqual((first['next_page'], first['exhausted'], first['raw_count']), (2, 0, 2))
        self.register_results(2, [{'number': 3}])
        self.assertEqual(self.run_original(), 0)
        second = self.row()
        self.assertEqual((second['next_page'], second['exhausted'], second['raw_count']), (3, 1, 3))
        self.assertEqual(second['status'], 'exhausted')
        count_calls = len(self.tape.calls)
        self.assertEqual(self.run_original(), 0)
        self.assertEqual(len(self.tape.calls), count_calls)  # no third API request

    def test_max_total_pages_caps_a_full_page(self):
        self.config['collection']['targeted_max_pages_total'] = 1
        self.register_results(1, [{'number': 1}, {'number': 2}])
        self.assertEqual(self.run_original(), 0)
        self.assertEqual((self.row()['next_page'], self.row()['exhausted']), (2, 1))

    def test_empty_page_is_exhausted_without_skipping_a_page(self):
        self.register_results(1, [])
        self.assertEqual(self.run_original(), 0)
        self.assertEqual((self.row()['next_page'], self.row()['exhausted']), (1, 1))
        self.assertEqual(self.row()['raw_count'], 0)

    def test_non_search_error_preserves_next_page_and_marks_error(self):
        self.register_results(1, [], status=500, error='GitHub temporarily unavailable')
        self.assertEqual(self.run_original(), 0)
        self.assertEqual((self.row()['status'], self.row()['next_page']), ('error', 1))
        self.register_results(1, [])
        self.assertEqual(self.run_original(), 0)
        self.assertEqual(self.row()['status'], 'exhausted')

    def test_1000_result_query_boundary_marks_exhausted(self):
        self.register_results(1, [], status=422,
                              error='Only the first 1000 search results are available')
        self.assertEqual(self.run_original(), 0)
        self.assertEqual(self.row()['exhausted'], 1)

    def test_missing_response_fails_closed_instead_of_fake_exhaustion(self):
        with self.assertRaises(IncompleteReplayError):
            self.run_original()
        self.assertEqual(self.row()['status'], 'running')
        self.assertEqual(self.row()['exhausted'], 0)

    def test_exhausted_query_does_not_require_a_fixture(self):
        self.db.execute('INSERT INTO retrieval_queries(stream_key,term,final_query,next_page,exhausted,status) '
                        'VALUES(?,?,?,?,?,?)', ('issue_links', 'fixes #', self.jobs()[0][2], 3, 1, 'exhausted'))
        self.assertEqual(self.run_original(), 0)
        self.assertEqual(len(self.tape.calls), 0)

    def test_non_disposable_db_is_refused_before_original_code(self):
        with TemporaryDirectory(prefix='unrelated_sqlite_') as temp:
            fake = Database(Path(temp)/'miner.sqlite', read_only=False)
            with self.assertRaises(ValueError):
                self.original['run'](db=fake, gh=self.gh, settings=self.settings)

    def test_non_fixture_github_is_refused(self):
        with self.assertRaises(TypeError):
            self.original['run'](db=self.db, gh=object(), settings=self.settings)

    def test_clock_sleep_is_recorded_not_executed(self):
        self.register_results(1, [])
        with mock.patch('time.sleep', side_effect=AssertionError('real sleep')):
            self.assertEqual(self.run_original(), 0)
        self.assertEqual(self.original['clock'].sleeps, [1.0])

    def _fixture_valid_pr(self):
        return {
            'number': 12, 'html_url': 'https://example.invalid/example/repo/pull/12',
            'title': 'Fixes #8', 'body': 'Fixes #8\nRepair build system',
            'state': 'closed', 'merged_at': '2026-10-10T12:00:00Z',
            'head': {'ref': 'codex/repair', 'sha': 'abc'},
            'base': {'ref': 'main', 'sha': 'def'},
            'user': {'login': 'alice'}, 'additions': 4, 'changed_files': 1,
        }

    def _register_valid_case(self):
        q = self.jobs()[0][2]
        self.register_results(1, [{
            'number': 12,
            'pull_request': {'url': 'https://api.github.com/repos/example/repo/pulls/12'},
            'repository_url': 'https://api.github.com/repos/example/repo',
        }], query=q)
        self.tape.add('GET', '/repos/example/repo', data={
            'full_name': 'example/repo', 'html_url': 'https://example.invalid/example/repo',
            'stargazers_count': 900, 'language': 'TypeScript', 'archived': False,
        })
        self.tape.add('GET', '/repos/example/repo/pulls/12', data=self._fixture_valid_pr())
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1},
                      data=[{'filename': 'src/runner.ts', 'status': 'modified', 'additions': 4}])
        self.tape.add('GET', '/repos/example/repo/issues/8', data={
            'number': 8, 'id': 8008,
            'html_url': 'https://example.invalid/example/repo/issues/8',
            'title': 'Build failure',
            'body': 'Please fix the failing build in src/runner.ts, rather than changing docs.',
            'state': 'open', 'created_at': '2026-10-01T00:00:00Z',
            'user': {'login': 'bob'}, 'labels': [],
        })
        return q

    def test_full_archived_targeted_query_creates_case_and_retrieval_link(self):
        q = self._register_valid_case()
        self.assertEqual(self.run_original(), 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM cases')['n'], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM case_retrievals')['n'], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM ai_markers')['n'], 1)
        row = self.row(q)
        self.assertEqual((row['next_page'], row['exhausted'], row['eligible_count'], row['candidate_count']),
                         (2, 1, 1, 1))  # one partial page advances cursor to 2; exhausted
        self.assertEqual(row['status'], 'exhausted')
        self.assertEqual(self.db.one('SELECT final_query FROM case_retrievals')['final_query'], q)

    def test_second_targeted_query_reuses_case_without_duplicate_marker(self):
        self.config['collection']['targeted_max_terms'] = 2
        queries = self.jobs()
        self.assertEqual(len(queries), 2)
        self._register_valid_case()
        # In _register_valid_case(), first query is registered, and second result is now added.
        self.register_results(1, [{
            'number': 12,
            'pull_request': {'url': 'https://api.github.com/repos/example/repo/pulls/12'},
            'repository_url': 'https://api.github.com/repos/example/repo',
        }], query=queries[1][2])
        self.assertEqual(self.run_original(), 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM cases')['n'], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM ai_markers')['n'], 1)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM case_retrievals')['n'], 2)
        self.assertEqual(self.db.one('SELECT COUNT(*) AS n FROM retrieval_queries')['n'], 2)


if __name__ == '__main__':
    unittest.main()
