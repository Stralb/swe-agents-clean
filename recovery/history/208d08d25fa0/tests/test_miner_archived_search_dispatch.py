"""Exact historical search and collect dispatcher, under synthetic-only services."""
from __future__ import annotations

import hashlib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src.github.replay_client import FixtureTransport, ReplayGitHubClient
from tests.support import archived_collection_contract as adapter
from tests.support.archived_pr_contract import IncompleteReplayError

UTC = timezone.utc
START = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def make_search_runner():
    funcs = adapter.load_original_adaptive_search()
    tape = FixtureTransport()
    gh = adapter.FixtureSearchOnly(ReplayGitHubClient(tape))
    return funcs, tape, gh


def add_page(tape, q, *, per_page, page=1, total_count=0, items=None, incomplete=False):
    tape.add('GET', '/search/issues', params={
        'q': q, 'sort': 'updated', 'order': 'desc', 'per_page': per_page, 'page': page},
        data={'total_count': total_count, 'incomplete_results': incomplete, 'items': [] if items is None else items})


def search_options(**overrides):
    defaults = dict(enabled=True, legacy_per_page=50, legacy_max_pages=1,
                    search_per_page=2, split_threshold=2, max_depth=8)
    defaults.update(overrides)
    return defaults


class FrozenSearchSourceTests(unittest.TestCase):
    def test_exact_source_hash_for_three_snapshots(self):
        blob = adapter.SOURCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(blob).hexdigest(), adapter.COLLECTOR_SHA256)
        archive = adapter.SOURCE_PATH.parents[5]
        for stamp in ('2026-08-17', '2026-08-19', '2026-10-20-live-export'):
            with self.subTest(stamp=stamp):
                self.assertEqual((archive/'historical/miner'/stamp/'src/pipeline/collect_pipeline.py').read_bytes(), blob)

    def test_corrupted_source_aborts_before_compilation(self):
        with TemporaryDirectory(prefix='arno_corrupted_') as temp:
            source = Path(temp)/'bad.py'
            source.write_text('print("UNAPPROVED")\n')
            with mock.patch.object(adapter, 'SOURCE_PATH', source):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    adapter.load_original_adaptive_search()
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    adapter.load_original_dispatch(adapter.DispatchSpies())

    def test_rejects_non_fixture_github_client(self):
        funcs, tape, gh = make_search_runner()
        with self.assertRaises(TypeError):
            list(funcs['run'](object(), 'is:pr', START.isoformat(), end_at=START,
                              **search_options()))
        with self.assertRaises(TypeError):
            adapter.FixtureSearchOnly(object())

    def test_missing_page_fixture_is_not_treated_as_exhaustion(self):
        funcs, tape, gh = make_search_runner()
        with self.assertRaises(IncompleteReplayError):
            list(funcs['run'](gh, 'is:pr', START.isoformat(), end_at=START,
                              **search_options()))


class OriginalWindowArithmeticTests(unittest.TestCase):
    def test_merged_qualifier_replaced_including_case_insensitive_version(self):
        funcs, _, _ = make_search_runner()
        q = funcs['_bounded_merged_query']('is:pr MERGED:>=2025-01-01  language:Python',
                                           START, START + timedelta(seconds=3))
        self.assertEqual(q, 'is:pr language:Python merged:2026-10-01T12:00:00Z..2026-10-01T12:00:03Z')

    def test_split_covers_every_inclusive_second_once(self):
        funcs, _, _ = make_search_runner()
        split = funcs['_split_agentic_window'](START, START + timedelta(seconds=7))
        left, right = split
        self.assertEqual(left[0], START)
        self.assertEqual(right[1], START + timedelta(seconds=7))
        self.assertEqual(right[0], left[1] + timedelta(seconds=1))
        covered = list(range(int((left[0]-START).total_seconds()), int((left[1]-START).total_seconds())+1))
        covered += list(range(int((right[0]-START).total_seconds()), int((right[1]-START).total_seconds())+1))
        self.assertEqual(covered, list(range(8)))
        self.assertIsNone(funcs['_split_agentic_window'](START, START))

    def test_naive_merged_since_assumed_utc_and_reformatted(self):
        funcs, _, _ = make_search_runner()
        self.assertEqual(funcs['_parse_agentic_lookback']('2026-10-01T12:00:00'), START)
        self.assertEqual(funcs['_github_search_timestamp'](START), '2026-10-01T12:00:00Z')


class OriginalAdaptiveSearchTests(unittest.TestCase):
    def test_first_count_probe_is_also_page_one_without_duplicate_request(self):
        funcs, tape, gh = make_search_runner()
        query = funcs['_bounded_merged_query']('is:pr merged:>=2025-01-01', START, START)
        add_page(tape, query, per_page=2, total_count=2, items=[{'id': 1}, {'id': 2}])
        stats = {}
        actual = list(funcs['run'](gh, 'is:pr merged:>=2025-01-01', START.isoformat(),
                                    end_at=START, stats=stats, **search_options()))
        self.assertEqual(actual, [{'id': 1}, {'id': 2}])
        self.assertEqual(len(tape.calls), 1)
        self.assertEqual(stats, {'search_window_count': 1, 'split_window_count': 0,
                                  'probe_count': 1, 'reported_total_count': 2})

    def test_pagination_starts_at_second_page_after_probe(self):
        funcs, tape, gh = make_search_runner()
        query = funcs['_bounded_merged_query']('is:pr', START, START)
        add_page(tape, query, per_page=2, total_count=5, items=[1, 2])
        add_page(tape, query, per_page=2, page=2, items=[3, 4])
        add_page(tape, query, per_page=2, page=3, items=[5])
        stats = {}
        got = list(funcs['run'](gh, 'is:pr', START.isoformat(), end_at=START, stats=stats,
                                **search_options(split_threshold=999)))
        self.assertEqual(got, [1, 2, 3, 4, 5])
        self.assertEqual([dict(__import__('json').loads(c.params))['page'] for c in tape.calls], [1, 2, 3])
        self.assertEqual(stats['probe_count'], 1)
        self.assertEqual(stats['reported_total_count'], 5)

    def test_recursive_split_for_incomplete_window_yields_left_then_right(self):
        funcs, tape, gh = make_search_runner()
        start, end = START, START + timedelta(seconds=5)
        broad = funcs['_bounded_merged_query']('is:pr', start, end)
        (ls, le), (rs, re) = funcs['_split_agentic_window'](start, end)
        left = funcs['_bounded_merged_query']('is:pr', ls, le)
        right = funcs['_bounded_merged_query']('is:pr', rs, re)
        add_page(tape, broad, per_page=2, total_count=999, incomplete=True, items=['discarded-probe'])
        add_page(tape, left, per_page=2, total_count=1, items=['left'])
        add_page(tape, right, per_page=2, total_count=1, items=['right'])
        stats = {}
        got = list(funcs['run'](gh, 'is:pr', start.isoformat(), end_at=end, stats=stats, **search_options()))
        self.assertEqual(got, ['left', 'right'])
        self.assertEqual(stats, {'search_window_count': 2, 'split_window_count': 1,
                                  'probe_count': 3, 'reported_total_count': 2})
        self.assertEqual(tape.unconsumed_count(), 0)

    def test_irreducible_one_second_window_raises_explicitly(self):
        funcs, tape, gh = make_search_runner()
        query = funcs['_bounded_merged_query']('is:pr', START, START)
        add_page(tape, query, per_page=2, total_count=15)
        with self.assertRaisesRegex(RuntimeError, 'one-second GitHub search window'):
            list(funcs['run'](gh, 'is:pr', START.isoformat(), end_at=START, **search_options()))

    def test_maximum_split_depth_error(self):
        funcs, tape, gh = make_search_runner()
        end = START + timedelta(seconds=7)
        root = funcs['_bounded_merged_query']('is:pr', START, end)
        left_start, left_end = funcs['_split_agentic_window'](START, end)[0]
        left = funcs['_bounded_merged_query']('is:pr', left_start, left_end)
        add_page(tape, root, per_page=2, total_count=4)
        add_page(tape, left, per_page=2, total_count=4)
        with self.assertRaisesRegex(RuntimeError, 'max split depth'):
            list(funcs['run'](gh, 'is:pr', START.isoformat(), end_at=end,
                              **search_options(max_depth=1)))

    def test_disabled_windowing_uses_legacy_search_without_count_probe(self):
        funcs, tape, gh = make_search_runner()
        q = 'is:pr'
        p = {'q': q, 'sort': 'updated', 'order': 'desc', 'per_page': 3, 'page': 1}
        tape.add('GET', '/search/issues', params=p, data={'items': [1, 2]})
        stats = {}
        opts = search_options()
        opts.update(enabled=False, legacy_per_page=3, legacy_max_pages=1)
        got = list(funcs['run'](gh, q, START.isoformat(), end_at=START, stats=stats, **opts))
        self.assertEqual(got, [1, 2])
        self.assertEqual(stats['probe_count'], 0)

    def test_future_start_produces_no_search(self):
        funcs, tape, gh = make_search_runner()
        got = list(funcs['run'](gh, 'is:pr', START.isoformat(),
                                end_at=START-timedelta(seconds=1), **search_options()))
        self.assertEqual(got, [])
        self.assertEqual(tape.calls, [])

    def test_seven_day_presplit_has_shared_inclusive_boundary_and_stats_reset(self):
        """Original behaviour is deliberately regression-pinned, NOT corrected."""
        funcs, tape, gh = make_search_runner()
        start = START
        end = start + timedelta(days=14, seconds=1)
        first_end = start + timedelta(days=7)
        second_end = start + timedelta(days=14)
        q1 = funcs['_bounded_merged_query']('is:pr', start, first_end)
        q2 = funcs['_bounded_merged_query']('is:pr', first_end, second_end)
        q3 = funcs['_bounded_merged_query']('is:pr', second_end, end)
        # One synthetic PR dated on the shared inclusive boundary returns twice.
        add_page(tape, q1, per_page=2, total_count=1, items=['boundary-case'])
        add_page(tape, q2, per_page=2, total_count=1, items=['boundary-case'])
        add_page(tape, q3, per_page=2, total_count=0, items=[])
        stats = {}
        got = list(funcs['run'](gh, 'is:pr', start.isoformat(), end_at=end,
                                stats=stats, **search_options()))
        self.assertEqual(got, ['boundary-case', 'boundary-case'])
        self.assertEqual(len(tape.calls), 3)
        self.assertEqual(stats['probe_count'], 1)  # last chunk only; prior counts overwritten
        self.assertEqual(stats['reported_total_count'], 0)
        self.assertEqual(stats['search_window_count'], 1)


class ArchivedCollectorDispatchTests(unittest.TestCase):
    def _run(self, mode, *, ai_only=False, discovery='hybrid', repo_walk=False, limit_reached=False):
        spies = adapter.DispatchSpies(limiter=lambda *a: limit_reached)
        original = adapter.load_original_dispatch(spies)
        cfg = {'collection': {'retrieval_mode': mode, 'ai_only': ai_only,
                              'ai_discovery': discovery, 'repo_walk_enabled': repo_walk}}
        self.assertIsNone(original(adapter.fixture_settings(cfg)))
        return spies

    def _handlers(self, spies):
        return [x[0] for x in spies.calls if x[0].startswith('_collect_')]

    def test_every_repo_month_alias_selects_original_mode(self):
        aliases = ('repo_month', 'repo_month_pr_search', 'repo_window', 'repo_window_pr_search',
                   'repo_window_adaptive', 'repo_universe', 'downstream_first')
        for mode in aliases:
            with self.subTest(mode=mode):
                spies = self._run(mode, ai_only=True, repo_walk=True)
                self.assertEqual(self._handlers(spies), ['_collect_repo_month_pr_search'])

    def test_every_targeted_alias_prioritized_even_with_ai_only(self):
        aliases = ('targeted', 'streams', 'stream', 'targeted_pr_search', 'wide', 'wide_first')
        for mode in aliases:
            with self.subTest(mode=mode):
                spies = self._run(mode, ai_only=True)
                self.assertEqual(self._handlers(spies), ['_collect_targeted_stream_search'])

    def test_ai_search_and_hybrid_dispatch(self):
        self.assertEqual(self._handlers(self._run('unknown', ai_only=True, discovery='search',repo_walk=True)),
                         ['_collect_ai_search'])
        self.assertEqual(self._handlers(self._run('unknown', ai_only=True, discovery='hybrid',repo_walk=True)),
                         ['_collect_ai_search', '_collect_repo_walk'])

    def test_hybrid_passes_first_case_count_to_repo_walk(self):
        spies = self._run('unknown', ai_only=True, discovery='hybrid', repo_walk=True)
        repo_walk = [call for call in spies.calls if call[0]=='_collect_repo_walk'][0]
        self.assertEqual(repo_walk[2]['initial_case_count'], 13)
        self.assertEqual(len(spies.limits), 1)
        self.assertEqual(spies.limits[0][0][3], 13)

    def test_hybrid_skips_repo_walk_if_budget_exhausted(self):
        spies = self._run('unknown', ai_only=True, discovery='hybrid', repo_walk=True, limit_reached=True)
        self.assertEqual(self._handlers(spies), ['_collect_ai_search'])

    def test_unknown_mode_repo_walk_or_targeted_fallback(self):
        self.assertEqual(self._handlers(self._run('unknown', repo_walk=True)), ['_collect_repo_walk'])
        self.assertEqual(self._handlers(self._run('unknown', repo_walk=False)), ['_collect_targeted_stream_search'])

    def test_constructor_is_inert_and_rate_db_disabled(self):
        spies = self._run('targeted')
        self.assertEqual([x[0] for x in spies.calls[:2]], ['database_ctor', 'github_ctor'])
        self.assertEqual(spies.client_kwargs['rate_db_path'], None)
        self.assertTrue(spies.client_token_seen)
        self.assertEqual(spies.client_kwargs['min_remaining'], 100)
        self.assertEqual(spies.client_kwargs['search_min_remaining'], 2)

    def test_distributed_cooldown_path_is_constructed_without_file_access(self):
        spies = adapter.DispatchSpies()
        spies.fake_environ['DISTRIBUTED_SPOOL_ROOT'] = '/synthetic/spool'
        caller = adapter.load_original_dispatch(spies)
        with mock.patch('builtins.open', side_effect=AssertionError('filesystem read')):
            self.assertIsNone(caller(adapter.fixture_settings({'collection': {'retrieval_mode': 'targeted'}})))
        self.assertEqual(spies.client_kwargs['secondary_cooldown_path'], '/synthetic/spool/github_secondary_cooldown.json')

    def test_refuses_an_unapproved_real_token_or_database_path(self):
        spies = adapter.DispatchSpies()
        cfg = adapter.fixture_settings({'collection': {'retrieval_mode': 'targeted'}})
        cfg.db_path = '/tmp/real.sqlite'
        with self.assertRaises(ValueError):
            adapter.load_original_dispatch(spies)(cfg)
