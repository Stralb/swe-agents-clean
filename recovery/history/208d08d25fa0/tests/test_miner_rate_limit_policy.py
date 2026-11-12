"""Offline rate-budget arithmetic and exact historical edge behaviour."""
from __future__ import annotations

import ast
from pathlib import Path
import unittest
from unittest import mock

from src.github.rate_limit_policy import RateSnapshot, parse_rate_headers, reserve_for, seconds_until_safe


class RateLimitPolicyTests(unittest.TestCase):
    def test_missing_or_malformed_headers_do_not_produce_snapshot(self):
        self.assertIsNone(parse_rate_headers({}))
        self.assertIsNone(parse_rate_headers({'X-RateLimit-Remaining': 'what', 'X-RateLimit-Reset': '22'}))

    def test_case_header_forms_and_core_default(self):
        row = parse_rate_headers({'X-RateLimit-Remaining': '30', 'X-RateLimit-Limit': '5000', 'X-RateLimit-Reset': '1234'})
        self.assertEqual(row, RateSnapshot('core', 5000, 30, 1234))
        lower = parse_rate_headers({'x-ratelimit-remaining': '1', 'x-ratelimit-limit': '30', 'x-ratelimit-reset': '1234', 'x-ratelimit-resource': 'search'})
        self.assertEqual(lower.resource, 'search')

    def test_core_reserve_does_not_apply_to_search(self):
        self.assertEqual(reserve_for('core', limit_value=5000, min_remaining=100, search_min_remaining=2), 100)
        self.assertEqual(reserve_for('search', limit_value=30, min_remaining=100, search_min_remaining=2), 2)
        self.assertEqual(reserve_for('search', limit_value=30, min_remaining=100, search_min_remaining=9), 3)

    def test_search_zero_reserve_does_not_wait_on_one_remaining(self):
        row = RateSnapshot('search', 30, 1, 200)
        self.assertEqual(seconds_until_safe(row, now=100, search_min_remaining=0), 0)
        self.assertEqual(seconds_until_safe(RateSnapshot('search', 30, 0, 200), now=100, search_min_remaining=0), 102)

    def test_core_wait_threshold_is_inclusive(self):
        self.assertEqual(seconds_until_safe(RateSnapshot('core', 5000, 101, 300), now=200), 0)
        self.assertEqual(seconds_until_safe(RateSnapshot('core', 5000, 100, 300), now=200), 102)

    def test_expired_reset_still_returns_minimum_one(self):
        self.assertEqual(seconds_until_safe(RateSnapshot('search', 30, 0, 70), now=100), 1)

    def test_disabled_state_does_not_block(self):
        self.assertEqual(seconds_until_safe(None, now=100), 0)

    def test_negative_reserves_normalized_as_constructor_did(self):
        self.assertEqual(reserve_for('core', min_remaining=-10), 0)
        self.assertEqual(reserve_for('search', limit_value=30, search_min_remaining=-10), 0)

    def test_explicit_now_and_no_filesystem_operations(self):
        row = RateSnapshot('core', 5000, 0, 200)
        with mock.patch('builtins.open', side_effect=AssertionError('file access')):
            with mock.patch('time.sleep', side_effect=AssertionError('unexpected wait')):
                self.assertEqual(seconds_until_safe(row, now=100), 102)
