"""Original OSV/Trivy advisory matching and PR attribution: synthetic only."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import (
    ArchivedFixtureScanCase, FixtureScannerProviders,
)
from tests.support.archived_dependency_snapshot_pure import (
    OSV_PATH, OSV_SHA256, TRIVY_PATH, TRIVY_SHA256,
    load_original_osv_attribution, load_original_trivy_attribution,
)


class OriginalSnapshotAttributionPureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osv = load_original_osv_attribution()
        cls.trivy = load_original_trivy_attribution()

    def test_original_sources_match_all_three_archives_exactly(self):
        root = Path(__file__).resolve().parents[1]
        for scanner, sha in [("osv_scanner.py", OSV_SHA256),
                             ("trivy_scanner.py", TRIVY_SHA256)]:
            original = root / "historical/miner/2026-10-20-live-export/src/scanners" / scanner
            data = original.read_bytes()
            for stamp in ("2026-08-17", "2026-08-19", "2026-10-20-live-export"):
                with self.subTest(scanner=scanner, stamp=stamp):
                    other = root / "historical/miner" / stamp / "src/scanners" / scanner
                    self.assertEqual(other.read_bytes(), data)
                    self.assertEqual(hashlib.sha256(other.read_bytes()).hexdigest(), sha)

    def test_original_attribution_loader_does_not_expose_scanning_execution(self):
        for methods in (self.osv, self.trivy):
            self.assertFalse(any(key.startswith("scan_") for key in methods))
            self.assertTrue(methods)
            for func in methods.values():
                self.assertNotIn("run_cmd", func.__globals__)
                self.assertNotIn("subprocess", func.__globals__)
                self.assertNotIn("shutil", func.__globals__)

    def test_osv_base_and_head_path_membership_and_renames(self):
        files = [
            {"filename": "backend/pyproject.toml", "status": "modified"},
            {"filename": "frontend/package.json", "status": "added"},
            {"filename": "legacy/requirements.txt", "status": "removed"},
            {"filename": "new/poetry.lock", "previous_filename": "old/poetry.lock",
             "status": "renamed"},
            {"filename": "src/main.py", "status": "modified"},
        ]
        before = self.osv["_dependency_paths_for_snapshot"](files, after=False)
        after = self.osv["_dependency_paths_for_snapshot"](files, after=True)
        self.assertEqual(
            before, ["backend/pyproject.toml", "legacy/requirements.txt", "old/poetry.lock"]
        )
        self.assertEqual(
            after, ["backend/pyproject.toml", "frontend/package.json", "new/poetry.lock"]
        )
        self.assertEqual(
            self.osv["_rename_aliases"](files),
            {"new/poetry.lock": "old/poetry.lock"},
        )

    def test_osv_renamed_snapshot_finding_matches_original_path_alias(self):
        raw = {"aliases": ["GHSA-SYNTHETIC"], "related": ["CVE-SYNTHETIC"]}
        base = {"file": "old/poetry.lock", "package": "FixtureLib",
                "vuln_id": "OSV-SYNTHETIC", "raw": raw}
        head = dict(base, file="new/poetry.lock")
        self.assertNotEqual(
            self.osv["_snapshot_finding_key"](base),
            self.osv["_snapshot_finding_key"](head),
        )
        self.assertEqual(
            self.osv["_snapshot_finding_key"](base),
            self.osv["_snapshot_finding_key"](
                head, path_aliases={"new/poetry.lock": "old/poetry.lock"},
            ),
        )
        self.assertEqual(
            self.osv["_advisory_ids"](base),
            ("CVE-SYNTHETIC", "GHSA-SYNTHETIC", "OSV-SYNTHETIC"),
        )

    def test_osv_alias_subset_changes_entire_key_even_with_shared_id(self):
        base = {"file": "pkg/requirements.txt", "package": "synthetic_lib",
                "vuln_id": "OSV-1", "raw": {"aliases": ["GHSA-1"]}}
        head = {"file": "pkg/requirements.txt", "package": "synthetic_lib",
                "vuln_id": "OSV-1", "raw": {}}
        self.assertNotEqual(
            self.osv["_snapshot_finding_key"](base),
            self.osv["_snapshot_finding_key"](head),
        )

    def test_osv_path_traversal_is_rejected_by_path_normalizer(self):
        self.assertEqual(self.osv["_normalise_dependency_path"]("../secret.txt"), "")
        self.assertEqual(
            self.osv["_normalise_dependency_path"]("./pkg/requirements.txt"),
            "pkg/requirements.txt",
        )
        self.assertEqual(
            self.osv["_dependency_ancestor_directories"]("src/pkg/pyproject.toml"),
            ["src/pkg", "src", ""],
        )

    def test_status_priority_and_all_inapplicable_disagree_across_scanners(self):
        self.assertEqual(self.osv["_snapshot_status"]("timeout", "error"), "error")
        self.assertEqual(self.trivy["_combined_status"]("timeout", "error"), "timeout")
        self.assertEqual(self.osv["_snapshot_status"](
            "not_applicable", "not_applicable"
        ), "ok")
        self.assertEqual(self.trivy["_combined_status"](
            "not_applicable", "not_applicable"
        ), "not_applicable")
        self.assertEqual(self.trivy["_combined_status"](
            "ok", "ok_with_warnings"
        ), "ok_with_warnings")

    def test_trivy_overlapping_advisory_aliases_count_as_preexisting(self):
        base = {
            "file": "pkg/requirements.txt", "package": "fixture_lib",
            "package_path": "", "vuln_id": "CVE-SYNTHETIC",
            "raw": {"Aliases": ["GHSA-SYNTHETIC"]},
        }
        head = {
            "file": "pkg/requirements.txt", "package": "fixture_lib",
            "package_path": "", "vuln_id": "GHSA-SYNTHETIC",
        }
        self.assertEqual(
            self.trivy["_snapshot_delta_findings"]([base], [head]), []
        )

    def test_trivy_new_advisory_must_match_changed_pr_target(self):
        finding = {
            "file": "pkg/requirements.txt", "package": "fixture_lib",
            "package_path": "", "vuln_id": "CVE-NEW-SYNTHETIC",
            "evidence": {"target": "pkg/requirements.txt"},
        }
        self.assertEqual(
            self.trivy["_introduced_findings"](
                [], [finding], ["pkg/not-the-same.lock"]
            ),
            [],
        )
        introduced = self.trivy["_introduced_findings"](
            [], [finding], ["pkg/requirements.txt"]
        )
        self.assertEqual(len(introduced), 1)
        self.assertEqual(
            (introduced[0]["introduced"], introduced[0]["diff_linked"]),
            (1, True),
        )
        self.assertEqual(introduced[0]["evidence"]["pr_attributable"], True)
        self.assertEqual(
            introduced[0]["evidence"]["attribution_reason"],
            "target_changed_by_pr",
        )

    def test_trivy_empty_advisory_id_is_not_proven_preexisting(self):
        base = {"file": "requirements.txt", "package": "fixture_lib"}
        head = dict(base)
        self.assertEqual(len(self.trivy["_snapshot_delta_findings"]([base], [head])), 1)

    def test_trivy_path_suffix_matching_can_be_ambiguous(self):
        self.assertTrue(self.trivy["_trivy_paths_equal"](
            "/workspace/pkg/requirements.txt", "pkg/requirements.txt"
        ))
        self.assertTrue(self.trivy["_trivy_paths_equal"](
            "/workspace/pkg/requirements.txt", "requirements.txt"
        ))
        self.assertEqual(
            self.trivy["_trivy_normalise_path"](".github/workflows/check.yml"),
            "github/workflows/check.yml",
        )

    def test_pure_loader_refuses_mutated_osv_before_compilation(self):
        import tests.support.archived_dependency_snapshot_pure as source
        with TemporaryDirectory(prefix="arno_bad_osv_") as td:
            bad = Path(td) / "osv_scanner.py"
            bad.write_text("print('UNEXPECTED EXECUTION')\n", encoding="utf-8")
            with mock.patch.object(source, "OSV_PATH", bad):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    source.load_original_osv_attribution()

    def test_pure_loader_refuses_mutated_trivy_before_compilation(self):
        import tests.support.archived_dependency_snapshot_pure as source
        with TemporaryDirectory(prefix="arno_bad_trivy_") as td:
            bad = Path(td) / "trivy_scanner.py"
            bad.write_text("print('UNEXPECTED EXECUTION')\n", encoding="utf-8")
            with mock.patch.object(source, "TRIVY_PATH", bad):
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    source.load_original_trivy_attribution()

    def test_trivy_original_introduction_flows_into_disposable_scan_case(self):
        finding = {
            "file": "fixture/requirements.txt", "package": "synthetic_lib",
            "package_path": "", "vuln_id": "CVE-SYNTHETIC-INTRO",
            "evidence": {"target": "fixture/requirements.txt"},
        }
        introduced = self.trivy["_introduced_findings"](
            [], [finding], ["fixture/requirements.txt"]
        )
        self.assertEqual(len(introduced), 1)
        with disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/trivy-path",
                "html_url": "https://example.invalid/fixture/trivy-path",
            })
            pr = db.upsert_pr(repo, {
                "number": 4, "html_url": "https://example.invalid/fixture/trivy-path/pull/4",
                "base": {"ref": "main", "sha": "synthetic-base"},
                "head": {"ref": "fixture", "sha": "synthetic-head"},
            })
            issue = db.upsert_issue(repo, {
                "number": 2, "html_url": "https://example.invalid/fixture/trivy-path/issues/2",
                "title": "synthetic only", "body": "synthetic only", "labels": [],
            }, 2, True)
            db.link_issue_pr(issue, pr, "synthetic")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, [{
                "filename": "fixture/requirements.txt",
                "status": "modified", "category": "dependency",
                "patch": "@@ -1 +1 @@\n-synthetic_lib==2.0\n+synthetic_lib==2.5\n",
                "additions": 1,
            }])
            case = {
                "case_id": case_id, "pr_id": pr,
                "repo_url": "https://example.invalid/fixture/trivy-path",
                "base_sha": "synthetic-base", "head_sha": "synthetic-head",
            }
            backend = FixtureScannerProviders(trivy=[(
                introduced, {"status": "ok"}, {"status": "ok"}, {"status": "ok"},
            )])
            ArchivedFixtureScanCase(db, backend).run(case, {
                "scanners": {
                    "gitleaks": False, "dependency_downgrade": False,
                    "osv": False, "trivy": True, "semgrep": False,
                    "codeql": False,
                },
                "cache": {"force_rescan": False},
            })
            row = db.one(
                "SELECT scanner,finding_type,introduced,rule_id,evidence "
                "FROM scanner_findings WHERE case_id=?", (case_id,),
            )
            self.assertEqual(
                (row["scanner"], row["finding_type"], row["introduced"], row["rule_id"]),
                ("trivy-scanner", "dependency", 1, "CVE-SYNTHETIC-INTRO"),
            )
            self.assertIn("pr_attributable", row["evidence"])


if __name__ == "__main__":
    unittest.main()
