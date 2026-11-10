"""No-I/O configuration preview regression tests with synthetic mappings."""
import ast
import copy
from pathlib import Path
import unittest
from unittest import mock

from src.runtime.config_preview import preview_settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "synthetic-project"
HISTORICAL = ROOT / "historical/miner/2026-10-20-live-export/src/settings.py"


class PreviewTests(unittest.TestCase):
    def test_relative_default_and_explicit_absolute_paths(self):
        a = preview_settings(FIXTURE_ROOT, {"database": {"path": "db/archive.sqlite"}}, {})
        self.assertEqual(a.config_path, FIXTURE_ROOT / "config.yml")
        self.assertEqual(a.db_path, FIXTURE_ROOT / "db/archive.sqlite")
        absolute = FIXTURE_ROOT / "local" / "copy.sqlite"
        b = preview_settings(FIXTURE_ROOT, {"database": {"path": "ignored"}}, {
            "CONFIG": "other.yml", "DB_PATH": str(absolute)})
        self.assertEqual(b.config_path, FIXTURE_ROOT / "other.yml")
        self.assertEqual(b.db_path, absolute)

    def test_tokens_redacted_and_precedence_retained(self):
        x = preview_settings(FIXTURE_ROOT, {}, {
            "GITHUB_TOKENS": "", "GITHUB_TOKEN": "PRIVATE_123", "GH_TOKEN": "ALSO_PRIVATE"})
        self.assertEqual(x.token_source, "GITHUB_TOKEN")
        self.assertNotIn("PRIVATE_123", repr(x))
        self.assertNotIn("ALSO_PRIVATE", repr(x))
        self.assertIsNone(preview_settings(FIXTURE_ROOT, {}, {}).token_source)

    def test_runtime_limits_and_invalid_integer(self):
        x = preview_settings(FIXTURE_ROOT, {"collection": {"max_cases_per_repo": 12}}, {
            "MAX_CASES_PER_REPO": "bad", "MAX_REPOS": "3", "MAX_PRS": "-5",
            "MAX_CASES": "", "MAX_SECONDS": "invalid"})
        self.assertEqual(x.limits.max_cases_per_repo, 12)
        self.assertEqual(x.limits.max_repos, 3)
        self.assertEqual(x.limits.max_prs, -5)
        self.assertIsNone(x.limits.max_cases)
        self.assertIsNone(x.limits.max_seconds)

    def test_github_language_override_precedence(self):
        config = {"github": {"language": "Python", "languages": ["Python", "Go"]}}
        x = preview_settings(FIXTURE_ROOT, config, {"GITHUB_LANGUAGE": "JavaScript"})
        self.assertEqual((x.github_language, x.github_languages), ("JavaScript", ("JavaScript",)))
        x = preview_settings(FIXTURE_ROOT, config, {"GITHUB_LANGUAGES": "TypeScript, JavaScript"})
        self.assertEqual((x.github_language, x.github_languages), ("TypeScript", ("TypeScript", "JavaScript")))
        x = preview_settings(FIXTURE_ROOT, config, {
            "GITHUB_LANGUAGE": "Python", "GITHUB_LANGUAGES": "JavaScript,TypeScript"})
        self.assertEqual((x.github_language, x.github_languages), ("Python", ("JavaScript", "TypeScript")))

    def test_scanner_booleans_do_not_mutate_source_config(self):
        config = {"scanners": {"codeql": False}}
        before = copy.deepcopy(config)
        x = preview_settings(FIXTURE_ROOT, config, {
            "SCAN_CODEQL": "TRUE", "SCAN_SEMGREP": "0", "SCAN_OSV": ""})
        self.assertEqual(dict(x.scanner_env_overrides), {"codeql": True, "semgrep": False})
        self.assertEqual(config, before)

    def test_invalid_mapping_and_root(self):
        with self.assertRaises(ValueError):
            preview_settings(Path("relative"), {}, {})
        with self.assertRaises(TypeError):
            preview_settings(FIXTURE_ROOT, [], {})
        with self.assertRaises(TypeError):
            preview_settings(FIXTURE_ROOT, {"database": ["wrong"]}, {})
        with self.assertRaises(ValueError):
            preview_settings(FIXTURE_ROOT, {}, {"DB_PATH": "~/would-require-ambient-home"})

    def test_no_access_to_ambient_env_or_directory_creation(self):
        with mock.patch("os.getenv", side_effect=AssertionError("ambient environment read")):
            with mock.patch.object(Path, "mkdir", side_effect=AssertionError("write attempt")):
                x = preview_settings(FIXTURE_ROOT, {}, {})
        self.assertEqual(x.db_path, FIXTURE_ROOT / "data/miner.db")

    def test_archived_loader_is_stateful_and_not_active(self):
        source = HISTORICAL.read_text(encoding="utf-8")
        tree = ast.parse(source)
        self.assertTrue(any(
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "load_dotenv"
            for node in tree.body))
        self.assertIn("db_path.parent.mkdir(", source)
        self.assertFalse((ROOT / "src/settings.py").exists())
