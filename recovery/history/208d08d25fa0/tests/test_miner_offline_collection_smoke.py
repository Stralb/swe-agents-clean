"""Exercise real byte-preserved collection helpers through deterministic API fixtures.

Synthetic programming smoke test; deliberately not historical cohort replication.
"""
from __future__ import annotations

import unittest

from src.filters.bot_filter import is_excluded_bot
from src.filters.issue_filters import passes_issue_filters
from src.filters.pr_filters import classify_pr_files
from src.github.issue_linker import find_linked_issue_numbers
from src.github.replay_client import FixtureTransport, MissingFixtureError, ReplayGitHubClient
from src.markers.ai_markers import detect_ai_markers
from src.pipeline.agentic_discovery import build_agentic_query_jobs, validate_pr_for_job


class CollectionContractTests(unittest.TestCase):
    def setUp(self):
        self.transport = FixtureTransport()
        self.github = ReplayGitHubClient(self.transport)
        jobs = build_agentic_query_jobs(
            languages=['TypeScript'], min_stars=200,
            merged_since='2025-01-01', maintenance_authors=['renovate[bot]'],
        )
        self.codex_job = next(j for j in jobs if j.indicator.key == 'codex_head')

    def test_candidate_data_can_flow_without_external_io(self):
        repo = 'owner/repo'
        pr = {
            'number': 7, 'title': 'Fixes #17', 'body': 'Fixes #17',
            'head': {'ref': 'codex/repair-17'}, 'user': {'login': 'human'},
        }
        issue = {'number': 17, 'title': 'Fix failing build', 'body': 'Please repair the failing build script.'}
        files = [{'filename': 'src/app.py'}]
        self.transport.add('GET', '/repos/owner/repo/pulls/7', data=pr)
        self.transport.add('GET', '/repos/owner/repo/issues/17', data=issue)
        self.transport.add('GET', '/repos/owner/repo/pulls/7/files', params={'page': 1, 'per_page': 50}, data=files)

        collected = self.github.get('/repos/owner/repo/pulls/7')
        self.assertEqual(validate_pr_for_job(collected, self.codex_job), (True, 'ok'))
        marker, hits = detect_ai_markers({'pr_branch': collected['head']['ref']}, {
            'ai_markers': {'high_confidence': ['codex/']}})
        self.assertEqual(marker, 'AI-explicit-high')
        self.assertEqual(len(hits), 1)
        self.assertEqual(find_linked_issue_numbers(collected['title'], collected['body'], current_repo=repo), [(17, 'closing-keyword')])
        the_issue = self.github.get('/repos/owner/repo/issues/17')
        self.assertTrue(passes_issue_filters(the_issue, 3, False)[0])
        self.assertFalse(is_excluded_bot(collected['user']['login'], collected['title'], collected['head']['ref'], ['dependabot']))
        self.assertEqual(classify_pr_files(list(self.github.paginate('/repos/owner/repo/pulls/7/files'))), 'behaviour_affecting')
        self.assertEqual(len(self.transport.calls), 3)

    def test_missing_issue_fixture_does_not_silently_pass(self):
        with self.assertRaises(MissingFixtureError):
            self.github.get('/repos/owner/repo/issues/17')

    def test_bot_exclusion_retains_original_semantics(self):
        self.assertTrue(is_excluded_bot('renovate[bot]', 'Updated deps', 'automated', ['renovate']))
