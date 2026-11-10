"""Actual pinned CodeQL engine and security-extended queries, synthetic only.

Archive bytes are unchanged. This is opt-in GitHub CI under Docker --network
none and a read-only repository mount. The source fixture is never executed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest

from src.db.disposable_harness import disposable_original_database
from tests.support.archived_fixture_scan_case import FixtureScannerProviders
from tests.support.archived_fixture_worker import (
    ArchivedFixtureWorker, FixtureWorkerSettings,
)
from tests.support.archived_job_queue_contract import load_original_queue
from tests.support.archived_real_codeql_local import (
    REPO_URL, FILENAME, SUITE, RealPinnedCodeQLReplay,
)

VERSION = "2.27.3"


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_REAL_CODEQL") == "1",
    "Requires checksum-verified CodeQL bundle and network-disabled test job",
)
class GenuineCodeQLArchivedPythonWorkflowTests(unittest.TestCase):
    def test_original_worker_runs_real_codeql_and_attributes_inert_injected_sink(self):
        binary = Path(os.environ["ARNO_REAL_CODEQL_BINARY"]).resolve()
        self.assertTrue(binary.is_file())
        self.assertEqual(binary.name, "codeql")
        self.assertEqual(Path(shutil.which("codeql") or "").resolve(), binary)
        version = subprocess.run(
            [str(binary), "version"], text=True,
            capture_output=True, timeout=40, check=True,
        )
        self.assertIn(VERSION, version.stdout + version.stderr)

        with RealPinnedCodeQLReplay() as replay, disposable_original_database() as db:
            repo = db.insert_or_get_repo({
                "full_name": "fixture/real-codeql",
                "html_url": REPO_URL,
            })
            pr = db.upsert_pr(repo, {
                "number": 8,
                "html_url": REPO_URL + "/pull/8",
                "base": {"ref": "main", "sha": replay.base_sha},
                "head": {"ref": "inert-test", "sha": replay.head_sha},
            })
            issue = db.upsert_issue(repo, {
                "number": 7,
                "html_url": REPO_URL + "/issues/7",
                "title": "Synthetic-only CodeQL static analysis",
                "body": "Only an inert unsafe source snippet, never executed",
                "labels": [],
            }, 5, True)
            db.link_issue_pr(issue, pr, "fabricated")
            case_id = db.create_or_get_case(repo, issue, pr, "AI-unknown", [])
            db.replace_pr_files(pr, replay.files())

            class GenuineCodeQLProvider(FixtureScannerProviders):
                def __init__(self):
                    super().__init__()
                    self.invocations = 0
                    self.responses = []

                def scan_snapshot_with_codeql(
                    self, repo_url, sha, *, language, build_mode,
                    query_suite, timeout_seconds,
                ):
                    self.invocations += 1
                    findings, metadata = replay.scan(
                        repo_url, sha, language=language,
                        build_mode=build_mode, query_suite=query_suite,
                        timeout_seconds=timeout_seconds,
                    )
                    self.responses.append((sha, findings, metadata))
                    return findings, metadata

            q = load_original_queue(db)
            self.assertEqual(q["seed_scanner_jobs"](db), 6)
            job = q["claim_job"](
                db, ["codeql"], worker_id="genuine-codeql-synthetic-only",
            )
            provider = GenuineCodeQLProvider()
            ArchivedFixtureWorker(db, provider).run(
                job, FixtureWorkerSettings({
                    "scanners": {
                        "gitleaks": False, "dependency_downgrade": False,
                        "osv": False, "trivy": False,
                        "semgrep": False, "codeql": False,
                        "codeql_language": "auto",
                        "codeql_timeout_seconds": 600,
                        "codeql_trigger": "all_codeql",
                    },
                    "cache": {"force_rescan": False},
                }),
            )
            self.assertEqual(provider.invocations, 2, provider.responses)
            self.assertEqual(
                [item[2]["status"] for item in provider.responses],
                ["ok", "ok"], provider.responses,
            )
            self.assertEqual(provider.responses[0][1], [])
            head = provider.responses[1][1]
            self.assertTrue(head, "Expected actual security-extended CodeQL warnings")
            print("Real CodeQL findings:", [
                {"rule": f.get("rule"), "file": f.get("file"),
                 "line": f.get("line"), "cwe": f.get("cwe"),
                 "description": str(f.get("description", ""))[:110]}
                for f in head
            ])
            findings = db.query(
                "SELECT scanner,finding_type,rule_id,cwe,file_path,line,raw_json "
                "FROM scanner_findings WHERE case_id=?",
                (case_id,),
            )
            self.assertTrue(
                any(
                    row["scanner"] == "codeql"
                    and row["finding_type"] == "vulnerability"
                    and str(row["cwe"] or "")
                    and row["file_path"] == FILENAME
                    and row["line"] is not None
                    for row in findings
                ),
                {"head": head, "db": findings},
            )
            runs = db.query(
                "SELECT scanner,status,stdout FROM scanner_runs "
                "WHERE case_id=? ORDER BY id",
                (case_id,),
            )
            self.assertEqual(
                [(row["scanner"], row["status"]) for row in runs],
                [
                    ("codeql-python-base", "ok"),
                    ("codeql-python-head", "ok"),
                    ("codeql-base", "ok"),
                    ("codeql-head", "ok"),
                    ("codeql", "ok"),
                ],
            )
            self.assertIn("security_diff_linked=", runs[-1]["stdout"])
            self.assertEqual(
                db.one(
                    "SELECT status FROM scanner_jobs WHERE id=?", (job.id,),
                )["status"], "ok",
            )
            self.assertEqual(
                db.one(
                    "SELECT status FROM cases WHERE id=?", (case_id,),
                )["status"], "needs_review",
            )


if __name__ == "__main__":
    unittest.main()
