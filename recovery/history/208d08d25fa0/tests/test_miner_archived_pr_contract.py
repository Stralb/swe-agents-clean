"""Execute exact historical _process_pr only with replay fixtures and new SQLite DB.

No network, Wits paths, Slurm, scanner tools or full collector entrypoint.
"""
from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from unittest import mock
from types import SimpleNamespace
from unittest.mock import patch
import time

from src.db.disposable_harness import disposable_original_database
from src.db.ephemeral import open_ephemeral_database
from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from tests.support.archived_pr_contract import (
    SOURCE_PATH, ORIGINAL_COLLECTOR_SHA256, FixtureOnlyGitHub,
    IncompleteReplayError, load_original_process_pr,
)
from src.pipeline.offline_case_collection import FixtureCollectionPolicy, collect_fixture_pr


class HistoricalProcessPRContractTest(unittest.TestCase):
    def setUp(self):
        self.history = disposable_original_database()
        self.db = self.history.__enter__()
        self.addCleanup(self.history.__exit__, None, None, None)
        self.tape = FixtureTransport()
        self.client = FixtureOnlyGitHub(ReplayGitHubClient(self.tape))
        self.process = load_original_process_pr()
        self.repo = {
            'full_name': 'example/repo', 'html_url': 'https://example.invalid/example/repo',
            'stargazers_count': 900, 'language': 'TypeScript',
        }
        self.pr = {
            'number': 12, 'html_url': 'https://example.invalid/example/repo/pull/12',
            'title': 'Fixes #8', 'body': 'Resolve build failure linked to #8',
            'state': 'closed', 'merged_at': '2026-10-10T12:00:00Z',
            'head': {'ref': 'codex/repair', 'sha': 'abcd'},
            'base': {'ref': 'main', 'sha': 'defg'},
            'user': {'login': 'alice'}, 'additions': 4, 'changed_files': 1,
        }
        self.issue = {
            'number': 8, 'id': 1208,
            'html_url': 'https://example.invalid/example/repo/issues/8',
            'title': 'Unexpected regression',
            'body': 'Build test fails after update. Please repair src/runner.ts.',
            'state': 'closed', 'labels': [{'name': 'bug'}], 'comments': 2,
            'user': {'login': 'bob'}, 'created_at': '2026-10-01T10:00:00Z',
        }
        self.files = [{'filename':'src/runner.ts', 'status':'modified', 'additions':4, 'deletions':1}]
        self.cfg = {
            'github': {'include_merged_prs': True, 'include_closed_unmerged_prs': False},
            'filters': {
                'min_issue_words': 3, 'issue_min_body_chars': 0,
                'english_only': False, 'exclude_bots': [],
                'exclude_non_behaviour_only': True, 'exclude_docs_scope_only': True,
            },
            'collection': {
                'lookback_start': '2025-01-01',
                'log_excluded_cases': True,
                'require_primary_worker': False, 'require_high_yield_surface': False,
                'fetch_pr_comments_for_issue_links': False,
                'fetch_commit_messages_for_issue_links': False,
                'fetch_commit_messages_for_ai': False,
                'max_changed_files_for_evidence': 75,
                'max_linked_issues_per_pr_for_evidence': 1,
                'require_javascript_typescript_surface': True,
                'require_issue_quality_filter': True,
                'ai_only': True,
            },
            'ai_markers': {'high_confidence':['codex/'], 'medium_confidence': []},
        }
        self.limits = SimpleNamespace(max_cases_per_repo=None, max_cases=None, max_seconds=None)

    def settings(self, cfg=None):
        return SimpleNamespace(config=self.cfg if cfg is None else cfg, limits=self.limits)

    def add_fixtures(self, *, files=None, issue=None, issue_code=200, pr=None, add_pr=False):
        actual_pr = self.pr if pr is None else pr
        if add_pr:
            self.tape.add('GET', '/repos/example/repo/pulls/12', data=actual_pr)
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page':100,'page':1}, data=self.files if files is None else files)
        if issue_code == 200:
            self.tape.add('GET', '/repos/example/repo/issues/8', data=self.issue if issue is None else issue)
        else:
            self.tape.add('GET', '/repos/example/repo/issues/8', status_code=issue_code, body='not found')

    def run_original(self, *, pr=None, cfg=None, links=None, case_count=0, repo_case_count=None):
        with patch.dict('os.environ', {'EVIDENCE_STRICT_SURFACE':'0'}):
            return self.process(db=self.db, gh=self.client, settings=self.settings(cfg),
                                repo=self.repo, pr=self.pr if pr is None else pr,
                                start=time.time(), case_count=case_count, repo_case_count=repo_case_count, prefetched_links=links)

    def count(self, table):
        return self.db.one('SELECT count(*) AS n FROM ' + table)['n']

    def test_loads_only_frozen_function_definitions(self):
        self.assertEqual(hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest(), ORIGINAL_COLLECTOR_SHA256)
        self.assertEqual(self.process.__name__, '_process_pr')
        self.assertEqual(self.process.__module__, '_offline_archived_pr_contract')
        self.assertNotIn('src.pipeline.collect_pipeline', sys.modules)
        root = SOURCE_PATH.parents[5]
        for version in ('2026-08-17', '2026-08-19', '2026-10-20-live-export'):
            historical = root / 'historical/miner' / version / 'src/pipeline/collect_pipeline.py'
            self.assertEqual(hashlib.sha256(historical.read_bytes()).hexdigest(), ORIGINAL_COLLECTOR_SHA256)

    def test_unrecognised_source_is_rejected_before_compilation(self):
        from tests.support import archived_pr_contract as module
        with TemporaryDirectory(prefix='arno_corrupt_fixture_') as root:
            filename = Path(root) / 'collector.py'
            filename.write_text('print("NOT APPROVED")\n', encoding='utf-8')
            with mock.patch.object(module, 'SOURCE_PATH', filename):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    module.load_original_process_pr()

    def test_non_disposable_sqlite_database_is_rejected(self):
        from src.db.database import Database
        with TemporaryDirectory(prefix='not_a_research_harness_') as root:
            foreign = Database(Path(root) / 'miner.sqlite', read_only=False)
            with self.assertRaises(ValueError):
                self.process(db=foreign, gh=self.client, settings=self.settings(),
                             repo=self.repo, pr=self.pr, start=time.time(), case_count=0)

    def test_original_pr_case_persistence_and_markers(self):
        self.add_fixtures()
        self.assertEqual(self.run_original(), (1,1))
        for table in ('repos','pull_requests','issues','pr_files','issue_pr_links','cases','upstream_features','ai_markers'):
            with self.subTest(table=table):
                self.assertEqual(self.count(table), 1)
        row=self.db.one('SELECT ai_cohort, status FROM cases')
        self.assertEqual(row['status'], 'metadata_collected')
        self.assertEqual(row['ai_cohort'], 'AI-explicit-high')

    def test_matches_new_fixture_adapter_for_simple_case(self):
        self.add_fixtures()
        self.assertEqual(self.run_original(), (1,1))
        memory=open_ephemeral_database()
        self.addCleanup(memory.close)
        other_tape=FixtureTransport()
        for method,path,params,data in [
            ('GET','/repos/example/repo/pulls/12',None,self.pr),
            ('GET','/repos/example/repo/pulls/12/files',{'per_page':100,'page':1},self.files),
            ('GET','/repos/example/repo/issues/8',None,self.issue),
        ]:
            other_tape.add(method,path,params=params,data=data)
        policy=FixtureCollectionPolicy(
            ai_only=True, ai_marker_config={'ai_markers':{'high_confidence':['codex/']}},
            require_javascript_typescript_surface=True, require_issue_quality_filter=True,
            min_issue_words=3, lookback_start='2025-01-01',
        )
        result=collect_fixture_pr(memory,ReplayGitHubClient(other_tape),self.repo,12,policy=policy)
        self.assertTrue(result.accepted)
        for table in ('repos','pull_requests','issues','pr_files','issue_pr_links','cases','upstream_features','ai_markers'):
            with self.subTest(table=table):
                self.assertEqual(memory.execute('SELECT count(*) FROM '+table).fetchone()[0],self.count(table))
        self.assertEqual(memory.execute('SELECT ai_cohort FROM cases').fetchone()[0],self.db.one('SELECT ai_cohort FROM cases')['ai_cohort'])

    def test_missing_issue_fixture_aborts_even_when_original_catches_exception(self):
        self.tape.add('GET','/repos/example/repo/pulls/12/files',params={'per_page':100,'page':1},data=self.files)
        with self.assertRaises(IncompleteReplayError):
            self.run_original()
        self.assertEqual(self.count('cases'),0)
        # Original has already persisted PR metadata; unlike atomic new adapter.
        self.assertEqual(self.count('pull_requests'),1)

    def test_outside_pr_lookback_has_no_api_calls(self):
        self.assertEqual(self.run_original(pr={**self.pr,'merged_at':'2024-01-01T00:00:00Z'}),(0,0))
        self.assertEqual(self.count('repos'),0)
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'],'outside_lookback_pr')

    def test_docs_rejected_by_earlier_behaviour_filter(self):
        self.tape.add('GET','/repos/example/repo/pulls/12/files',params={'per_page':100,'page':1},data=[{'filename':'README.md'}])
        cfg={**self.cfg, 'collection':{**self.cfg['collection'],'require_javascript_typescript_surface':False}}
        self.assertEqual(self.run_original(cfg=cfg),(0,0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'],'non_behaviour_only')

    def test_original_missing_issue_404_leaves_partial_pr_metadata(self):
        self.add_fixtures(issue_code=404)
        self.assertEqual(self.run_original(),(0,0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'],'stale_or_missing_issue_reference')
        self.assertEqual(self.count('pull_requests'),1)
        self.assertEqual(self.count('cases'),0)

    def test_replaying_same_case_duplicates_original_ai_marker_records(self):
        self.add_fixtures()
        self.assertEqual(self.run_original(),(1,1))
        self.add_fixtures()
        self.assertEqual(self.run_original(),(1,1))
        self.assertEqual(self.count('cases'),1)
        self.assertEqual(self.count('ai_markers'),2)

    def test_linked_issue_date_gate_runs_after_pr_metadata_writes(self):
        self.add_fixtures(issue={**self.issue,'created_at':'2024-01-01T00:00:00Z'})
        self.assertEqual(self.run_original(),(0,0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'],'outside_lookback_issue')
        self.assertEqual(self.count('pull_requests'),1)
        self.assertEqual(self.count('issues'),0)

    def test_secondary_route_regression_has_no_effect_on_docs_early_exclusion(self):
        self.tape.add('GET','/repos/example/repo/pulls/12/files',params={'per_page':100,'page':1},data=[{'filename':'README.md'}])
        cfg={**self.cfg, 'collection':{**self.cfg['collection'],'require_primary_worker':True, 'require_javascript_typescript_surface':False}}
        self.assertEqual(self.run_original(cfg=cfg),(0,0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'],'non_behaviour_only')

    def test_historical_422_file_unavailability_is_excluded(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, status_code=422,
                      body='large diff unavailable')
        self.assertEqual(self.run_original(), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'pr_files_unavailable')
        self.assertEqual(self.count('repos'), 0)

    def test_missing_changed_files_fixture_aborts_instead_of_being_silently_excluded(self):
        with self.assertRaises(IncompleteReplayError):
            self.run_original()
        self.assertEqual(self.count('excluded_cases'), 0)

    def test_original_changed_file_scope_gate(self):
        files = [{'filename': 'src/runner.ts'}, {'filename': 'src/example.js'}]
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=files)
        cfg = {**self.cfg, 'collection': {**self.cfg['collection'], 'max_changed_files_for_evidence': 1}}
        self.assertEqual(self.run_original(cfg=cfg), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'pr_scope_too_large_for_evidence')
        self.assertEqual(self.count('repos'), 0)

    def test_issue_reference_from_pr_comments(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=self.files)
        self.tape.add('GET', '/repos/example/repo/issues/12/comments',
                      params={'per_page': 100, 'page': 1}, data=[{'body': 'Fixes #8'}])
        self.tape.add('GET', '/repos/example/repo/issues/8', data=self.issue)
        cfg = {**self.cfg, 'collection': {**self.cfg['collection'], 'fetch_pr_comments_for_issue_links': True}}
        changed = {**self.pr, 'title': 'Update build', 'body': 'No issue link'}
        self.assertEqual(self.run_original(pr=changed, cfg=cfg), (1, 1))
        self.assertEqual(self.count('cases'), 1)

    def test_issue_reference_from_pr_commit_messages(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=self.files)
        self.tape.add('GET', '/repos/example/repo/pulls/12/commits',
                      params={'per_page': 100, 'page': 1},
                      data=[{'commit': {'message': 'Fixes #8'}}])
        self.tape.add('GET', '/repos/example/repo/issues/8', data=self.issue)
        cfg = {**self.cfg, 'collection': {**self.cfg['collection'], 'fetch_commit_messages_for_issue_links': True}}
        changed = {**self.pr, 'title': 'Update build', 'body': 'No issue link'}
        self.assertEqual(self.run_original(pr=changed, cfg=cfg), (1, 1))
        self.assertEqual(self.db.one('SELECT method FROM issue_pr_links')['method'], 'closing-keyword')

    def test_prefetched_links_cause_multi_issue_gate_before_database_writes(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=self.files)
        self.assertEqual(self.run_original(links=[(8, 'graphql-closing-issue'), (9, 'graphql-closing-issue')]), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'ambiguous_multi_issue_pr')
        self.assertEqual(self.count('repos'), 0)

    def test_duplicate_prefetched_issue_references_are_deduplicated(self):
        self.add_fixtures()
        self.assertEqual(self.run_original(links=[(8, 'closing-keyword'), (8, 'graphql-closing-issue')]), (1, 1))
        self.assertEqual(self.count('cases'), 1)
        self.assertEqual(self.count('issue_pr_links'), 1)

    def test_default_body_length_gate_is_200_characters(self):
        self.add_fixtures()
        cfg = {**self.cfg, 'filters': {key: val for key, val in self.cfg['filters'].items() if key != 'issue_min_body_chars'}}
        self.assertEqual(self.run_original(cfg=cfg), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'issue_body_too_short')
        self.assertEqual(self.count('pull_requests'), 1)

    def test_failed_issue_quality_check_keeps_pr_row(self):
        self.add_fixtures(issue={**self.issue, 'body': 'short'})
        self.assertEqual(self.run_original(), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'issue_filter')
        self.assertEqual(self.count('pull_requests'), 1)

    def test_http_500_issue_is_logged_as_inaccessible_not_aborted(self):
        self.add_fixtures(issue_code=500)
        self.assertEqual(self.run_original(), (0, 0))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'inaccessible_issue')
        self.assertEqual(self.count('pull_requests'), 1)

    def test_original_case_count_cap_applies_after_pr_metadata_persistence(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=self.files)
        self.limits.max_cases = 1
        self.assertEqual(self.run_original(case_count=1), (1, 0))
        self.assertEqual(self.count('cases'), 0)
        self.assertEqual(self.count('pull_requests'), 1)

    def test_original_repo_cap_logs_exclusion_after_pr_metadata_persistence(self):
        self.tape.add('GET', '/repos/example/repo/pulls/12/files',
                      params={'per_page': 100, 'page': 1}, data=self.files)
        self.limits.max_cases_per_repo = 1
        self.assertEqual(self.run_original(repo_case_count=1), (0, 1))
        self.assertEqual(self.db.one('SELECT reason FROM excluded_cases')['reason'], 'over_repo_cap')
        self.assertEqual(self.count('cases'), 0)

    def test_live_github_client_rejected_before_execution(self):
        self.add_fixtures()
        with self.assertRaises(TypeError):
            self.process(db=self.db, gh=object(), settings=self.settings(),
                         repo=self.repo, pr=self.pr, start=time.time(), case_count=0)
        self.assertEqual(self.count('repos'), 0)

    def test_non_database_object_rejected_before_execution(self):
        with self.assertRaises(TypeError):
            self.process(db=object(), gh=self.client, settings=self.settings(),
                         repo=self.repo, pr=self.pr, start=time.time(), case_count=0)


if __name__=='__main__':
    unittest.main()
