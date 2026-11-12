"""Synthetic tests; none of the historical scripts are imported or run."""

import hashlib
from pathlib import Path
import unittest

from analysis.phase2_sarif_triage import changed_new_lines, compare

ROOT = Path(__file__).resolve().parents[1]
PATCH = """diff --git a/src/test.js b/src/test.js
--- a/src/test.js
+++ b/src/test.js
@@ -4,0 +5,2 @@
+new code
+other code
"""


def finding(fingerprint=None, *, uri="src/test.js", line=5, rule="js/redos"):
    row = {"ruleId": rule, "locations": [{"physicalLocation": {
        "artifactLocation": {"uri": uri}, "region": {"startLine": line}}}]}
    if fingerprint is not None:
        row["partialFingerprints"] = {"primaryLocationLineHash": fingerprint}
    return row


def sarif(*rows):
    return {"runs": [{"results": list(rows)}]}


class Phase2OfflineTriageTests(unittest.TestCase):
    def test_identical_fingerprint_not_reported_as_new(self):
        data = compare(sarif(finding("same")), sarif(finding("same")), PATCH)
        self.assertEqual(data["classifications"], {"MATCHED_UNIQUE_FINGERPRINT": 1})

    def test_new_fingerprint_overlaps_edit_but_does_not_establish_causation(self):
        data = compare(sarif(), sarif(finding("new")), PATCH)
        self.assertEqual(data["status"], "SCANNER_TRIAGE_ONLY_NOT_CAUSAL_PROOF")
        self.assertEqual(data["classifications"], {"UNMATCHED_UNIQUE_FINGERPRINT": 1})
        self.assertTrue(data["results"][0]["overlaps_added_or_modified_line"])

    def test_new_fingerprint_outside_edit_is_not_silently_negative(self):
        data = compare(sarif(), sarif(finding("outside", line=120)), PATCH)
        self.assertEqual(data["classifications"], {"UNMATCHED_UNIQUE_FINGERPRINT": 1})
        self.assertFalse(data["results"][0]["overlaps_added_or_modified_line"])

    def test_missing_fingerprint_is_explicitly_uncertain(self):
        data = compare(sarif(), sarif(finding(None)), PATCH)
        self.assertEqual(data["classifications"], {"UNVERIFIABLE_NO_STABLE_FINGERPRINT": 1})

    def test_duplicate_fingerprints_are_ambiguous(self):
        data = compare(sarif(), sarif(finding("repeated"), finding("repeated", line=6)), PATCH)
        self.assertEqual(data["classifications"], {"AMBIGUOUS_DUPLICATE_FINGERPRINT": 2})

    def test_percent_encoded_uri_and_all_top_level_locations(self):
        patch = PATCH.replace("src/test.js", "src/a file.js")
        data = compare(sarif(), sarif(finding("new", uri="file:///tmp/repo/src/a%20file.js")), patch)
        self.assertTrue(data["results"][0]["overlaps_added_or_modified_line"])

    def test_deletion_only_hunk_has_no_added_lines(self):
        text = "diff --git a/a b/a\n--- a/a\n+++ /dev/null\n@@ -1,2 +0,0 @@\n-x\n-y\n"
        self.assertEqual(changed_new_lines(text), {})

    def test_quoted_diff_header_refused(self):
        with self.assertRaises(ValueError):
            changed_new_lines('diff --git "a/a b" "b/a b"\n--- "a/a b"\n+++ "b/a b"\n@@ -1 +1 @@\n')

    def test_original_historical_script_hashes_are_unchanged(self):
        original = {
            "historical/codeql_phase2/evaluate_phase2.py": "0dcd9112ea5aa0c5fa490c313a24e405f02fe35219be8a7bb58639368a89225c",
            "historical/codeql_phase2/phase2_eval_v2.py": "0f4c12a28b57e47c6a9be7316b34a01879d22533e08f89bea558b4b25823301d",
        }
        for relative, expected in original.items():
            with self.subTest(file=relative):
                actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
