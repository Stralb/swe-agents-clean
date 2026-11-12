"""Historical CodeQL diff/SARIF attribution, synthetic only; no scanners."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from tests.support import archived_codeql_attribution_contract as original


class OriginalCodeQLAttributionTests(unittest.TestCase):
    def setUp(self):
        self.fn = original.load_original_codeql_attribution()
        self.source_file = {
            "filename": "src/app.ts",
            "patch": "@@ -4,2 +4,3 @@\n context\n-old\n+new\n+added\n",
        }

    def test_codeql_source_same_in_all_three_snapshots(self):
        raw = original.SOURCE_PATH.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), original.SOURCE_SHA256)
        root = Path(__file__).resolve().parents[1]
        for stamp in ("2026-08-17", "2026-08-19", "2026-10-20-live-export"):
            with self.subTest(stamp=stamp):
                self.assertEqual(raw, (root/"historical/miner"/stamp/"src/scanners/codeql_scanner.py").read_bytes())

    def test_only_pure_codeql_attribution_functions_loaded(self):
        self.assertEqual(set(self.fn), set(original.NAMES))
        self.assertNotIn("scan_snapshot_with_codeql", self.fn)
        self.assertNotIn("_codeql_tempdir", self.fn)
        self.assertNotIn("_codeql_preflight", self.fn)

    def test_languages_and_query_suite_from_historical_literals(self):
        files = [
            {"filename": "src/app.ts"},
            {"filename": "src/tests.py"},
            {"filename": "src/server.java"},
            {"filename": "docs/guide.md"},
        ]
        self.assertEqual(
            self.fn["codeql_languages_for_files"](files),
            ["python", "javascript-typescript", "java-kotlin"],
        )
        self.assertTrue(self.fn["has_python_source_changes"](files))
        self.assertTrue(self.fn["has_codeql_source_changes"](files))
        self.assertIn("javascript-security-extended",
                      self.fn["default_query_suite_for_language"]("javascript-typescript"))

    def test_unified_patch_counts_added_new_side_lines(self):
        line_map = self.fn["added_line_numbers_by_file"]([self.source_file])
        self.assertEqual(line_map, {"src/app.ts": {5, 6}})

    def test_windows_git_patch_paths_normalize(self):
        fn = self.fn["_norm_path"]
        self.assertEqual(fn("b\\src\\app.ts"), "src/app.ts")
        self.assertEqual(fn("./a/src/app.ts"), "src/app.ts")

    def test_primary_added_line_is_linked(self):
        added = self.fn["added_line_numbers_by_file"]([self.source_file])
        self.assertTrue(self.fn["finding_touches_added_lines"](
            {"file": "src/app.ts", "line": 5}, added))
        self.assertFalse(self.fn["finding_touches_added_lines"](
            {"file": "src/app.ts", "line": 4}, added))

    def test_related_and_codeflow_sarif_locations_are_extracted(self):
        loc = lambda uri, line: {
            "physicalLocation": {
                "artifactLocation": {"uri": uri},
                "region": {"startLine": line},
            },
        }
        sarif = {
            "locations": [loc("src/other.ts", 15), loc("src/other.ts", 15)],
            "relatedLocations": [loc("b/src/app.ts", 5)],
            "codeFlows": [{"threadFlows": [{"locations": [
                {"location": loc("src/app.ts", 6)}
            ]}]}],
        }
        locs = self.fn["_extract_all_locations"](sarif)
        self.assertEqual(
            locs,
            [{"file": "src/other.ts", "line": 15, "kind": "primary"},
             {"file": "src/app.ts", "line": 5, "kind": "related"},
             {"file": "src/app.ts", "line": 6, "kind": "codeflow"}],
        )

    def test_related_or_codeflow_location_can_link_finding(self):
        added = self.fn["added_line_numbers_by_file"]([self.source_file])
        finding = {
            "file": "src/other.ts", "line": 100,
            "locations": [
                {"file": "src/other.ts", "line": 100, "kind": "primary"},
                {"file": "src/app.ts", "line": 6, "kind": "codeflow"},
            ],
        }
        self.assertTrue(self.fn["finding_touches_added_lines"](finding, added))

    def test_missing_patch_excludes_even_cwe_bearing_finding(self):
        files = [{"filename": "src/app.ts", "patch": None}]
        findings = [{"file": "src/app.ts", "line": 5, "cwe": "CWE-79"}]
        self.assertEqual(self.fn["filter_findings_to_pr_delta"](findings, files), [])

    def test_diff_filter_only_keeps_exact_added_line_and_marks_it(self):
        rows = [
            {"file": "src/app.ts", "line": 5, "rule": "SYNTHETIC-A"},
            {"file": "src/app.ts", "line": 4, "rule": "SYNTHETIC-B"},
            {"file": "src/app.ts", "line": 100, "rule": "SYNTHETIC-C",
             "locations": [{"file": "src/app.ts", "line": 6, "kind": "related"}]},
        ]
        actual = self.fn["filter_findings_to_pr_delta"](rows, [self.source_file])
        self.assertEqual([row["rule"] for row in actual], ["SYNTHETIC-A", "SYNTHETIC-C"])
        self.assertTrue(all(row["diff_linked"] is True for row in actual))
        self.assertNotIn("diff_linked", rows[0])

    def test_diff_findings_ignores_shifted_lines(self):
        base = [{"rule": "rule-A", "file": "src/app.ts",
                 "description": "same issue", "line": 10}]
        head = [
            {"rule": "rule-A", "file": "src/app.ts",
             "description": "same issue", "line": 25},
            {"rule": "rule-A", "file": "src/app.ts",
             "description": "new issue", "line": 25},
        ]
        out = self.fn["diff_findings"](base, head)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["description"], "new issue")

    def test_diff_identity_same_message_rule_file_discards_distinct_cwe(self):
        base = [{"rule": "rule-A", "file": "src/app.ts",
                 "description": "duplicate summary", "cwe": "CWE-79"}]
        head = [{"rule": "rule-A", "file": "src/app.ts",
                 "description": "duplicate summary", "cwe": "CWE-89"}]
        self.assertEqual(self.fn["diff_findings"](base, head), [])

    def test_corrupt_original_file_is_rejected(self):
        with TemporaryDirectory(prefix="arno_codeql_corrupt_") as directory:
            bad = Path(directory) / "codeql_scanner.py"
            bad.write_text("print('DO_NOT_EXECUTE')\n")
            with mock.patch.object(original, "SOURCE_PATH", bad):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    original.load_original_codeql_attribution()
