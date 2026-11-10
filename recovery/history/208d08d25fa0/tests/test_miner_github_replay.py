"""Contract tests for an in-memory GitHub client; never touches network/disk."""
from __future__ import annotations

import unittest
from unittest import mock

from src.github.replay_client import (
    FixtureTransport, GitHubAPIError, MissingFixtureError, ReplayGitHubClient,
)


class GitHubReplayTests(unittest.TestCase):
    def setUp(self):
        self.tape = FixtureTransport()
        self.client = ReplayGitHubClient(self.tape)

    def test_missing_fixture_fails_closed(self):
        with self.assertRaises(MissingFixtureError):
            self.client.get('/repos/example/repo')
        self.assertEqual(len(self.tape.calls), 1)

    def test_explicit_transport_required(self):
        with self.assertRaises(TypeError):
            ReplayGitHubClient(None)

    def test_exact_get_request_and_immutable_fixture(self):
        response = {'items': [{'number': 2}]}
        self.tape.add('GET', '/search/issues', params={'q': 'test'}, data=response)
        self.assertEqual(self.client.get('/search/issues', {'q': 'test'}), response)
        self.assertEqual(response['items'][0]['number'], 2)

    def test_replay_response_cannot_be_mutated_to_change_next_response(self):
        self.tape.add('GET', '/repos/owner/repo', data={'name': 'repo'})
        self.tape.add('GET', '/repos/owner/repo', data={'name': 'repo'})
        self.client.get('/repos/owner/repo')['name'] = 'changed'
        self.assertEqual(self.client.get('/repos/owner/repo')['name'], 'repo')

    def test_only_expected_github_domain_is_supported(self):
        with self.assertRaises(ValueError):
            self.client.get('https://example.org/private')
        with self.assertRaises(ValueError):
            self.client.get('https://user:pass@api.github.com/repos/a/b')

    def test_resumed_pagination_count_not_absolute_page_index(self):
        base = {'q': 'x', 'per_page': 2}
        self.tape.add('GET', '/search/issues', params={**base, 'page': 9}, data={'items': [9, 10]})
        self.tape.add('GET', '/search/issues', params={**base, 'page': 10}, data={'items': [11, 12]})
        rows = list(self.client.paginate('/search/issues', base, max_pages=2, start_page=9))
        self.assertEqual(rows, [9, 10, 11, 12])
        self.assertEqual([c.path for c in self.tape.calls], ['/search/issues'] * 2)
        self.assertNotIn('page', base)

    def test_search_1000_boundary_stops_single_window(self):
        base = {'q': 'issue', 'sort': 'updated', 'order': 'desc', 'per_page': 2}
        self.tape.add('GET', '/search/issues', params={**base, 'page': 1}, data={'items': ['a', 'b']})
        self.tape.add('GET', '/search/issues', params={**base, 'page': 2}, status_code=422,
                      body='Only the first 1000 search results are available')
        self.assertEqual(list(self.client.search_issues('issue', per_page=2, max_pages=2)), ['a', 'b'])

    def test_other_422_propagates(self):
        params = {'q': 'issue', 'sort': 'updated', 'order': 'desc', 'per_page': 2, 'page': 1}
        self.tape.add('GET', '/search/issues', params=params, status_code=422,
                      body='Sorry, this diff is taking too long')
        with self.assertRaises(GitHubAPIError):
            list(self.client.search_issues('issue', per_page=2))

    def test_empty_or_short_page_ends_pagination(self):
        p = {'per_page': 3, 'page': 1}
        self.tape.add('GET', '/repos/a/b/pulls', params=p, data=[{'number': 1}])
        self.assertEqual(list(self.client.paginate('/repos/a/b/pulls', {'per_page': 3})), [{'number': 1}])
        self.assertEqual(len(self.tape.calls), 1)

    def test_response_without_list_is_rejected(self):
        self.tape.add('GET', '/search/issues', params={'per_page': 50, 'page': 1}, data={'error': 'no items'})
        with self.assertRaises(ValueError):
            list(self.client.paginate('/search/issues'))

    def test_repo_search_qualifiers_and_cap(self):
        params = {'q': 'language:Python', 'sort': 'stars', 'order': 'desc', 'per_page': 100, 'page': 1}
        self.tape.add('GET', '/search/repositories', params=params, data={'items': []})
        self.assertEqual(list(self.client.search_repos('language:Python', per_page=999)), [])
        self.assertEqual(len(self.tape.calls), 1)

    def test_search_page_preserves_total_and_incomplete(self):
        p = {'q': 'x', 'sort': 'updated', 'order': 'desc', 'per_page': 100, 'page': 3}
        self.tape.add('GET', '/search/issues', params=p,
                      data={'total_count': 1001, 'incomplete_results': True, 'items': [{'number': 6}]})
        d = self.client.search_issues_page('x', per_page=900, page=3)
        self.assertEqual(d, {'total_count': 1001, 'incomplete_results': True, 'items': [{'number': 6}]})

    def test_closed_pulls_filters_and_pagination(self):
        p = {'state': 'closed', 'sort': 'updated', 'direction': 'desc', 'per_page': 100, 'page': 1}
        self.tape.add('GET', '/repos/a/b/pulls', params=p, data=[{'number': 7, 'merged_at': None}])
        self.assertEqual(list(self.client.closed_pulls('a/b')), [{'number': 7, 'merged_at': None}])

    def test_graphql_hydration_and_errors(self):
        payload = {'query': 'query Sample { viewer { login } }', 'variables': {'limit': 1}}
        self.tape.add('POST', '/graphql', json_body=payload, data={'data': {'viewer': {'login': 'sample'}}})
        self.assertEqual(self.client.graphql(payload['query'], payload['variables'])['data']['viewer']['login'], 'sample')
        self.tape.add('POST', '/graphql', json_body=payload, data={'errors': [{'message': 'no access'}]})
        with self.assertRaises(GitHubAPIError) as raised:
            self.client.graphql(payload['query'], payload['variables'])
        self.assertEqual(raised.exception.status_code, 200)

    def test_rate_limit_no_cache_override_side_effect(self):
        self.tape.add('GET', '/rate_limit', data={'resources': {'search': {'remaining': 30}}})
        self.assertEqual(self.client.rate_limit()['resources']['search']['remaining'], 30)

    def test_response_sequence_consumed_strictly(self):
        self.tape.add('GET', '/repos/a/b', data={'name': 'b'})
        self.client.get('/repos/a/b')
        self.assertEqual(self.tape.unconsumed_count(), 0)
        with self.assertRaises(MissingFixtureError):
            self.client.get('/repos/a/b')

    def test_no_http_or_filesystem_access(self):
        self.tape.add('GET', '/repos/a/b', data={'name': 'safe'})
        with mock.patch('builtins.open', side_effect=AssertionError('file access')):
            with mock.patch('socket.create_connection', side_effect=AssertionError('network access')):
                self.assertEqual(self.client.get('/repos/a/b'), {'name': 'safe'})
