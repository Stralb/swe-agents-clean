"""Explicit temporary-workspace factory safety and cleanup tests."""
from __future__ import annotations

import unittest
from pathlib import Path

from src.db.disposable_harness import disposable_original_database


class DisposableOriginalDatabaseHarnessTests(unittest.TestCase):
    def test_only_fresh_temp_db_and_cleanup(self):
        with disposable_original_database() as db:
            path = db.path
            self.assertTrue(path.is_file())
            self.assertTrue(path.name == "miner.sqlite")
            self.assertTrue(path.parent.name.startswith("arno_disposable_original_db_"))
            self.assertEqual(db.one("SELECT COUNT(*) AS n FROM tags")["n"], 12)
            db.insert_or_get_repo({"full_name": "fixture/demo", "html_url": "https://example.invalid/fixture/demo"})
            self.assertEqual(db.one("SELECT COUNT(*) AS n FROM repos")["n"], 1)
        self.assertFalse(path.exists())
        self.assertFalse(path.parent.exists())

    def test_each_context_is_isolated(self):
        with disposable_original_database() as db:
            a = db.path
            db.insert_or_get_repo({"full_name": "fixture/demo", "html_url": "https://example.invalid/fixture/demo"})
        with disposable_original_database() as db:
            b = db.path
            self.assertNotEqual(a, b)
            self.assertEqual(db.one("SELECT COUNT(*) AS n FROM repos")["n"], 0)

    def test_cleanup_on_exception(self):
        path = None
        with self.assertRaisesRegex(RuntimeError, "fixture-only"):
            with disposable_original_database() as db:
                path = db.path
                self.assertTrue(path.exists())
                raise RuntimeError("fixture-only failure")
        self.assertIsNotNone(path)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
