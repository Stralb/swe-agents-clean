"""Regression tests for exact frozen region/routing source, including quirks.

These tests deliberately do NOT change historical admission decisions.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import unittest
from unittest import mock

from src.artifacts.regions import classify_files, profile_summary
from src.filters.tool_applicability import (
    PRIMARY_WORKER_KEYS,
    codeql_languages_for_paths, has_any_applicable_downstream_worker,
    has_high_yield_downstream_surface, has_primary_applicable_downstream_worker,
    high_yield_surface_reasons, route_reasons,
)

ROOT = Path(__file__).resolve().parents[1]
EXPECT = {
    'src/artifacts/regions.py': 'd5445509284912dd2809eca249123063016f644a8c70859e6ec9f530ea5e6e17',
    'src/filters/tool_applicability.py': '34053e60b685666f54bf6afb587e92850ccce3e87c5d59d9ae7efe5abfeffce0',
}
SNAPSHOTS = ('2026-08-17', '2026-08-19', '2026-10-20-live-export')


class HistoricalRoutingTests(unittest.TestCase):
    def test_source_identity(self):
        for rel, expected in EXPECT.items():
            with self.subTest(rel=rel):
                active = (ROOT / rel).read_bytes()
                self.assertEqual(hashlib.sha256(active).hexdigest(), expected)
                for stamp in SNAPSHOTS:
                    self.assertEqual(active, (ROOT / 'historical/miner' / stamp / rel).read_bytes())

    def test_artifact_region_on_code(self):
        regions = classify_files([{'filename': 'src/auth/login.ts'}])
        self.assertEqual([x.region for x in regions], ['source_code'])
        self.assertEqual(profile_summary(regions)['region_counts']['source_code'], 1)

    def test_codeql_language_detection(self):
        self.assertIn('javascript-typescript', codeql_languages_for_paths(['src/app.ts']))
        self.assertIn('python', codeql_languages_for_paths(['scripts/job.py']))

    def test_primary_route_keys_contains_nonexistent_key(self):
        routes = route_reasons([{'filename': 'README.md'}])
        self.assertIn('ci_security', PRIMARY_WORKER_KEYS)
        self.assertNotIn('ci_security', routes)
        self.assertIn('secret_ci', routes)
        self.assertEqual(routes['secret_ci'], 'not_applicable:no_secret_or_patch_scan_region')

    def test_original_primary_worker_check_is_vacuously_true_for_docs(self):
        # Exact historical behavior, not a recommendation: the missing key
        # makes .get(key, '') look applicable. Do NOT silently change the miner.
        docs = [{'filename': 'README.md'}]
        self.assertTrue(has_primary_applicable_downstream_worker(docs))
        routes = route_reasons(docs)
        self.assertTrue(all(routes.get(key, '').startswith('not_applicable:')
                            for key in PRIMARY_WORKER_KEYS if key in routes))

    def test_original_any_worker_check_includes_profile_summary(self):
        # artifact_profile is always a returned informational route and does
        # not begin with not_applicable:, so this can be true with no workers.
        docs = [{'filename': 'README.md'}]
        self.assertTrue(has_any_applicable_downstream_worker(docs))
        self.assertIn('artifact_profile', route_reasons(docs))

    def test_source_route_is_present_for_normal_code(self):
        paths = [{'filename': 'src/runner.ts'}]
        self.assertTrue(route_reasons(paths)['codeql'].startswith('artifact_regions='))

    def test_high_yield_respects_original_ambient_env(self):
        source = [{'filename': 'src/runner.ts'}]
        with mock.patch.dict(os.environ, {'EVIDENCE_STRICT_SURFACE': '0'}):
            self.assertTrue(has_high_yield_downstream_surface(source))
        with mock.patch.dict(os.environ, {'EVIDENCE_STRICT_SURFACE': '1'}):
            self.assertFalse(has_high_yield_downstream_surface(source))

    def test_sensitive_source_path_kept_under_strict_gate(self):
        with mock.patch.dict(os.environ, {'EVIDENCE_STRICT_SURFACE': '1'}):
            reasons = high_yield_surface_reasons([{'filename': 'src/auth/token.ts'}])
            self.assertTrue(any(x.startswith('security_path:') for x in reasons))

    def test_dependency_is_high_yield(self):
        self.assertTrue(has_high_yield_downstream_surface([{'filename': 'package-lock.json'}]))


if __name__ == '__main__':
    unittest.main()
