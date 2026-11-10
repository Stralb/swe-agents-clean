"""Synthetic tests of original miner collection helpers, without API or database I/O."""
from __future__ import annotations

import hashlib
from pathlib import Path
import unittest
from unittest import mock

from src.filters.bot_filter import is_excluded_bot
from src.filters.issue_filters import passes_issue_filters
from src.pipeline.agentic_discovery import AGENTIC_INDICATORS, build_agentic_query_jobs, validate_pr_for_job
from src.pipeline.repo_universe import (
    global_active_pr_query, lookback_window, maintenance_bot_exclusions,
    month_windows, repo_month_pr_query, shard_accept, star_band_queries,
)
from src.utils.text import contains_any, is_probably_english, short, word_count

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ("2026-08-17", "2026-08-19", "2026-10-20-live-export")
HASHES = {
    "src/filters/bot_filter.py": "4e3cd46ec7ccdef717390aa01f1ba6364b7c1bd23332e01b8b35135a5ded4cd9",
    "src/filters/issue_filters.py": "d37d61fafd111099fa8399b84bbc3fe280036f067a11b46b84dd7673b62c5328",
    "src/utils/text.py": "4d65162f82be5177317100e5467b78bc1843ef29e3a2d6a4711e7ec700c43f3f",
    "src/pipeline/repo_universe.py": "a0c378c7bc53600912321c68b4ac218792ca8d426c45a3d8413967adf1eb1429",
    "src/pipeline/agentic_discovery.py": "9d742f0f4391de060c8ed9e90f1c189497d0c77902b1ba271fa3f1f630b1acf8",
}


class CoreRecoveryIdentityTests(unittest.TestCase):
    def test_byte_exact_across_archives(self):
        for path, digest in HASHES.items():
            with self.subTest(path=path):
                active = (ROOT / path).read_bytes()
                self.assertEqual(hashlib.sha256(active).hexdigest(), digest)
                for date in SNAPSHOTS:
                    self.assertEqual(active, (ROOT / "historical" / "miner" / date / path).read_bytes())


class PureCollectionContractTests(unittest.TestCase):
    def test_bot_exclusion_case_insensitive(self):
        self.assertTrue(is_excluded_bot("renovate[bot]", "Update", "deps", ["Renovate"]))
        self.assertTrue(is_excluded_bot("developer", "Update dependencies", "dependabot/work", ["dependabot"]))
        self.assertFalse(is_excluded_bot("alice", "Fix crash", "fix/123", ["renovate"]))

    def test_issue_word_count_and_english_disabled(self):
        ok, info = passes_issue_filters({"title": "Bug", "body": "fix strange crash"}, 3, False)
        self.assertTrue(ok)
        self.assertEqual(info, {"word_count": 3, "is_english": True})
        ok, info = passes_issue_filters({"title": "Bug", "body": "fix crash"}, 3, False)
        self.assertFalse(ok)
        self.assertEqual(info["word_count"], 2)

    def test_optional_language_detection_fallback_is_explicit(self):
        with mock.patch("src.utils.text.detect_langs", None):
            self.assertTrue(is_probably_english("simple ascii text"))
            self.assertFalse(is_probably_english("漢字漢字漢字漢字漢字"))
            self.assertFalse(is_probably_english(""))

    def test_text_helper_contract(self):
        self.assertEqual(word_count(None), 0)
        self.assertEqual(word_count("Two words"), 2)
        self.assertEqual(contains_any("ABC xyz", ["bc", "jkl"]), ["bc"])
        self.assertEqual(short(" a \t b \n c "), "a b c")

    def test_month_windows_rollover(self):
        windows = month_windows("2024-01-23", 3)
        self.assertEqual([(w.start, w.end) for w in windows], [
            ("2024-01-01", "2024-02-01"), ("2024-02-01", "2024-03-01"),
            ("2024-03-01", "2024-04-01")])
        self.assertEqual(lookback_window("2024-12-24", 2).end, "2025-02-01")

    def test_repo_queries_preserve_expected_qualifiers(self):
        star_query = star_band_queries(language="TypeScript", pushed_since="2025-01-01")[0]
        self.assertIn("language:TypeScript stars:200..499", star_query)
        self.assertIn("pushed:>=2025-01-01", star_query)
        pr_query = repo_month_pr_query("owner/repo", month_windows("2024-01-01", 1)[0])
        self.assertIn("repo:owner/repo is:pr is:merged linked:issue", pr_query)
        self.assertIn("merged:2024-01-01..2024-02-01", pr_query)
        self.assertIn("-author:dependabot[bot]", pr_query)

    def test_sharding_repeatable_and_partitioned(self):
        value = "example/repo"
        selected = [i for i in range(7) if shard_accept(value, shard_count=7, shard_index=i)]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected, [i for i in range(7) if shard_accept(value, shard_count=7, shard_index=i)])
        self.assertTrue(shard_accept(value, shard_count=1, shard_index=0))

    def test_global_query_and_exclusions(self):
        query = global_active_pr_query(month_windows("2024-06-01", 1)[0], language="JavaScript", min_stars=50)
        self.assertIn("language:JavaScript stars:>=50", query)
        self.assertIn("linked:issue", query)
        self.assertEqual(maintenance_bot_exclusions(["example[bot]"]), "-author:example[bot]")

    def test_agentic_jobs_six_distinct_indicators(self):
        jobs = build_agentic_query_jobs(
            languages=["JavaScript", "Python"], min_stars=200, merged_since="2025-01-01",
            maintenance_authors=["renovate[bot]"])
        self.assertEqual(len(jobs), len(AGENTIC_INDICATORS))
        self.assertEqual(len(set(j.indicator.key for j in jobs)), len(jobs))
        for job in jobs:
            self.assertIn("is:pr is:merged linked:issue", job.query)
            self.assertIn("-author:renovate[bot]", job.query)

    def test_agentic_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):
            build_agentic_query_jobs(languages=["Python"], min_stars=200, merged_since="2025-01-01", maintenance_authors=[])
        with self.assertRaises(ValueError):
            build_agentic_query_jobs(languages=["TypeScript"], min_stars=-1, merged_since="2025-01-01", maintenance_authors=[])

    def test_agentic_pr_validation(self):
        jobs = build_agentic_query_jobs(languages=["TypeScript"], min_stars=200, merged_since="2025-01-01", maintenance_authors=[])
        by_key = {j.indicator.key: j for j in jobs}
        self.assertEqual(validate_pr_for_job(
            {"head": {"ref": "codex/fix"}, "user": {"login": "alice"}}, by_key["codex_head"]), (True, "ok"))
        self.assertFalse(validate_pr_for_job({"head": {"ref": "other/fix"}}, by_key["codex_head"])[0])
        self.assertFalse(validate_pr_for_job(
            {"head": {"ref": "copilot/fix"}, "user": {"login": "alice"}}, by_key["copilot_head_author"])[0])
        self.assertTrue(validate_pr_for_job(
            {"head": {"ref": "copilot/fix"}, "user": {"login": "copilot"}}, by_key["copilot_head_author"])[0])
        self.assertTrue(validate_pr_for_job(
            {"body": "Generated with Claude Code"}, by_key["claude_generated_body"])[0])
        self.assertFalse(validate_pr_for_job(
            {"body": "No generator"}, by_key["claude_generated_body"])[0])
