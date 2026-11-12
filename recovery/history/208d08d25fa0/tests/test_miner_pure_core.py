"""Synthetic regression tests for four byte-preserved, zero-I/O miner modules."""
from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
import unittest

from src.markers.ai_markers import detect_ai_markers
from src.markers.upstream_features import extract_upstream_features
from src.github.issue_linker import find_linked_issue_numbers
from src.filters.pr_filters import (
    categorize_file, classify_pr_files, is_docs_scope_only,
    has_javascript_typescript_surface,
)

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOTS = ("2026-08-17", "2026-08-19", "2026-10-20-live-export")
EXPECTED = {
    "src/markers/ai_markers.py": "76aa76fcb1b957bdcc6056c4dea674671c7c362a6a3e1031c8021fdd91327b40",
    "src/markers/upstream_features.py": "ac8f39e34987ce2d5bc3437b3c21c49b04a4290c07dcb84a5aca5c8ecf71646c",
    "src/github/issue_linker.py": "35e82c7c650fa727fb14db95054252096e517371b2f8e0e6c1b6a2e2c3eb009c",
    "src/filters/pr_filters.py": "49e6fe78df374eff6cb21094cc8ee1d9bfa197cf8feb24ab5289e9af9f202867",
}


class Phase1CoreTests(unittest.TestCase):
    def test_marker_high_priority_and_path_marker(self):
        cfg = {"ai_markers": {"high_confidence": ["codex/"], "medium_confidence": ["ChatGPT"]}}
        name, hits = detect_ai_markers({"branch": "codex/fix-bug", "body": "ChatGPT"}, cfg)
        self.assertEqual(name, "AI-explicit-high")
        self.assertEqual(len(hits), 2)
        self.assertEqual(hits[0].marker_location, "branch")

    def test_marker_boundary_and_phrase(self):
        cfg = {"ai_markers": {"high_confidence": [], "medium_confidence": ["Devin", "Claude Code"]}}
        self.assertEqual(detect_ai_markers({"issue": "widevine metadata"}, cfg)[0], "AI-unknown")
        label, hits = detect_ai_markers({"body": "Built with Claude Code"}, cfg)
        self.assertEqual(label, "AI-explicit-medium")
        self.assertEqual([h.marker_text for h in hits], ["Claude Code"])

    def test_marker_no_text(self):
        self.assertEqual(detect_ai_markers({"body": None}, {"ai_markers": {}}), ("AI-unknown", []))

    def test_upstream_feature_code_block_and_long_issue(self):
        body = "A" * 3100 + "\n```python\n" + "print(1)\n" * 150 + "```"
        flags = extract_upstream_features("Bug", body)
        self.assertTrue(flags["has_code_block"])
        self.assertTrue(flags["large_code_block"])
        self.assertTrue(flags["high_context_load"])
        self.assertGreater(flags["code_block_chars"], 1000)
        self.assertIn("feature_json", flags)

    def test_upstream_signals_are_not_filtering_the_issue(self):
        signals = extract_upstream_features("Regression", "The test fails. CVE-2026-1000.")
        self.assertIn("has_security_steering_signal", signals)
        self.assertIs(signals["has_security_steering_signal"], True)

    def test_issue_linker_same_repo_and_bare(self):
        self.assertEqual(
            find_linked_issue_numbers(
                "Fixes https://github.com/freqtrade/freqtrade/issues/123",
                current_repo="freqtrade/freqtrade",
            ),
            [(123, "closing-keyword")],
        )
        self.assertEqual(find_linked_issue_numbers("Fixes #84", current_repo="Zie619/n8n-workflows"),
                         [(84, "closing-keyword")])

    def test_issue_linker_ignores_third_party_changelog(self):
        self.assertEqual(find_linked_issue_numbers(
            "See https://github.com/pytest-dev/pytest/issues/4181",
            current_repo="freqtrade/freqtrade"), [])

    def test_issue_linker_deduplicates_references(self):
        refs = find_linked_issue_numbers("Closes #81 and issue #81", current_repo="a/b")
        self.assertEqual(refs, [(81, "closing-keyword")])

    def test_pr_file_categories(self):
        self.assertEqual(categorize_file("src/app.py"), "source")
        self.assertEqual(categorize_file("requirements.txt"), "dependency")
        self.assertEqual(classify_pr_files([{"filename": "README.md"}]), "non_behaviour_only")
        self.assertEqual(classify_pr_files([{"filename": "src/main.py"}]), "behaviour_affecting")
        self.assertEqual(classify_pr_files([{"filename": "data/schema.json"}]), "ambiguous")

    def test_docs_scope_exception(self):
        self.assertTrue(is_docs_scope_only([{"filename": "docs/conf.py"}]))
        self.assertFalse(is_docs_scope_only([{"filename": "docs/conf.py"},
                                             {"filename": "requirements.txt"}]))

    def test_javascript_surface(self):
        self.assertTrue(has_javascript_typescript_surface([{"filename": "src/component.tsx"}]))
        self.assertFalse(has_javascript_typescript_surface([{"filename": "docs/tutorial.md"}]))

    def test_promoted_bytes_match_three_historical_snapshots(self):
        for rel, expected in EXPECTED.items():
            with self.subTest(module=rel):
                active = (ROOT / rel).read_bytes()
                self.assertEqual(hashlib.sha256(active).hexdigest(), expected)
                for snapshot in SNAPSHOTS:
                    historical = ROOT / "historical" / "miner" / snapshot / rel
                    self.assertEqual(historical.read_bytes(), active)


if __name__ == "__main__":
    unittest.main()
