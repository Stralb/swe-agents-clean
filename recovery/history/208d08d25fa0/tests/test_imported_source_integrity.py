"""Preserved historical source bytes are checked, never executed or imported."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.verify_imported_sources import (
    ImportedSourceError, ROOT, _verify_file, main,
    safe_relative_path, verify_imported_sources,
)


class HistoricalImportIntegrityTests(unittest.TestCase):
    def test_all_original_imported_source_bytes_match_frozen_manifest(self):
        record = verify_imported_sources(ROOT)
        self.assertEqual(record["status"], "PASS_ARCHIVED_SOURCE_BYTES_ONLY")
        self.assertEqual(record["indexed_source_files_verified"], 1075)
        self.assertEqual(record["indexed_source_bytes_verified"], 11926471)
        self.assertEqual(record["additional_codeql_evaluators_verified"], 2)
        self.assertEqual(record["additional_evaluator_bytes_verified"], 24132)
        self.assertEqual(record["documentation_only_unindexed_paths"],
                         ["historical/README.md"])
        self.assertFalse(record["historical_files_executed"])
        self.assertFalse(record["historical_results_recomputed"])
        self.assertEqual(record["original_source_groups_verified"], {
            "DECISION_STEP7": 3, "DISCOVERY_V21": 14,
            "DISCOVERY_V22": 10, "MINER_AUG17": 210,
            "MINER_AUG19": 216, "MINER_LIVE": 518,
            "OCTOBER_JOBS": 104,
        })

    def test_reference_source_path_must_be_historical_and_canonical(self):
        good = "historical/miner/2026-10-20-live-export/src/scanners/codeql_scanner.py"
        self.assertEqual(safe_relative_path(good), good)
        for bad in (
            "/tmp/source.py", "src/scanners/active.py", "historical/../source.py",
            "historical//bad.py", "historical/./test.py",
            "historical\\miner\\source.py", "historical/",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ImportedSourceError):
                    safe_relative_path(bad)

    def test_synthetic_source_wrong_bytes_rejected(self):
        data = b"historical sample only, do not execute\n"
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            relative = "historical/dummy/sample.py"
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(data)
            _verify_file(root, relative, digest, len(data))
            target.write_bytes(data + b"altered")
            with self.assertRaisesRegex(ImportedSourceError, "byte size"):
                _verify_file(root, relative, digest, len(data))
            with self.assertRaisesRegex(ImportedSourceError, "Changed frozen"):
                _verify_file(root, relative, digest, len(data) + 7)

    def test_synthetic_symlink_with_correct_hash_still_rejected(self):
        original = b"synthetic"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "outside"
            file.write_bytes(original)
            dest = root / "historical" / "dummy" / "sample.py"
            dest.parent.mkdir(parents=True)
            dest.symlink_to(file)
            with self.assertRaisesRegex(ImportedSourceError, "Symlink"):
                _verify_file(root, "historical/dummy/sample.py",
                             hashlib.sha256(original).hexdigest(), len(original))

    def test_fake_sha256_string_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / "historical" / "dummy" / "sample.py"
            dest.parent.mkdir(parents=True)
            dest.write_bytes(b"x")
            with self.assertRaisesRegex(ImportedSourceError, "Invalid source SHA-256"):
                _verify_file(root, "historical/dummy/sample.py", "bad", 1)

    def test_cli_prints_explicit_source_only_status(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--repository", str(ROOT)])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result["status"], "PASS_ARCHIVED_SOURCE_BYTES_ONLY")
        self.assertFalse(result["historical_results_recomputed"])


if __name__ == "__main__":
    unittest.main()
