"""Read-only synthetic fixtures for static miner dependency inventory."""
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.miner_import_inventory import get_modules, describe_module, inspect

PFX = "historical/miner/2026-10-20-live-export/"


def fixture(path, files):
    with ZipFile(path, "w") as z:
        for rel, body in files.items():
            z.writestr(PFX + rel, body)


class MinerImportInventoryTests(unittest.TestCase):
    def test_snapshot_inventory_classifies_sibling_local_and_external(self):
        with tempfile.TemporaryDirectory() as home:
            p = Path(home) / "sample.zip"
            fixture(p, {
                "analysis/stage/a.py": "from deep_common import ok\nimport pandas\nimport pathlib\n",
                "analysis/stage/deep_common.py": "def ok():\n    return 1\n",
                "src/main.py": "from src.utils import thing\nimport requests\n",
                "src/utils/__init__.py": "pass\n",
                "tests/test_x.py": "assert 1\n",
            })
            summary, rows = inspect(p)
            self.assertEqual(summary["python_files"], 5)
            self.assertEqual(summary["parse_fail"], 0)
            self.assertIn("pandas", summary["third_party_imported_top_level_modules"])
            self.assertNotIn("deep_common", summary["third_party_imported_top_level_modules"])
            item = next(r for r in rows if r["module"] == "analysis.stage.a")
            self.assertIn("<sibling>:deep_common", item["local_imports"])

    def test_invalid_syntax_flagged_without_executing(self):
        invalid = describe_module("scripts/bad.py", b"if :\n  x\n", {"scripts.bad"})
        self.assertEqual(invalid["parse_status"], "FAIL")

    def test_mutating_calls_are_conservative_hints(self):
        source = b"from pathlib import Path\ndef save(p):\n    Path(p).unlink()\n"
        row = describe_module("src/edit.py", source, {"src.edit"})
        self.assertIn("unlink", row["risky_call_hints"])
        self.assertEqual(row["top_level_calls"], "")

    def test_top_level_side_effect_detected_but_main_guard_is_ignored(self):
        a = describe_module("scripts/collect.py", b"collect()\n", {"scripts.collect"})
        b = describe_module("scripts/gated.py", b"if __name__ == '__main__':\n    collect()\n", {"scripts.gated"})
        self.assertEqual(a["top_level_calls"], "collect")
        self.assertEqual(b["top_level_calls"], "")

    def test_unindexed_member_cannot_leak_into_python_inventory(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            fixture(path, {"src/x.py": "x = 1", "backups/old.py": "x = 2"})
            with ZipFile(path) as z:
                names = get_modules(z)
            self.assertEqual(list(names), ["src/x.py"])

    def test_no_runtime_or_filesystem_actions_from_readonly_checker(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sample.zip"
            fixture(path, {"src/x.py": "from src import z\n"})
            initial = sorted(p.name for p in Path(folder).iterdir())
            inspect(path)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), initial)


if __name__ == "__main__":
    unittest.main()
