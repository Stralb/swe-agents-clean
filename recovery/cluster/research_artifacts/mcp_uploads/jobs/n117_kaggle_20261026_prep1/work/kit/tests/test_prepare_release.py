import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "prepare_release.py"
spec = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseSafetyTests(unittest.TestCase):
    def test_refuses_non_matching_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "candidate.py"
            p.write_text("not our frozen agent\n")
            with self.assertRaisesRegex(ValueError, "verification FAILED"):
                module.verify_sha(p, "0" * 64)

    def test_exact_hash_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "candidate.py"
            p.write_bytes(b"checked bytes\n")
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(module.verify_sha(p, digest), digest)

    def test_missing_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                module.verify_sha(Path(tmp) / "nonexistent.ipynb", "0" * 64)

    def test_no_unverified_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
                module.build(Path(tmp), Path(tmp) / "output", "arnostrauss", "n117-test")

    def test_source_mismatch_fails_even_if_notebook_parses(self):
        nb = {"nbformat": 4, "cells": [{"source": ""} for _ in range(5)]}
        with self.assertRaisesRegex(ValueError, "embedded agent differs"):
            module.verify_notebook(nb, "unverified agent")

    def test_list_form_supported(self):
        self.assertEqual(module.cell_source({"source": ["alpha", "beta"]}), "alphabeta")


if __name__ == "__main__":
    unittest.main()
