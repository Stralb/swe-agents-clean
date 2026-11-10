"""Opt-in real Trivy 0.76.1 against a checksum-pinned public DB snapshot.

No network in test container. Only fixed public Python package versions and
original SHA-verified _scan_snapshot / _introduced_findings functions are used.
This is an ENGINE/DB compatibility gate, not the historical miner DB.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tests.support.archived_trivy_local_process import _load_original_trivy
from tests.test_miner_real_dependency_engines import _original_shell, _allowlisted_binary

TRIVY_VERSION = "0.76.1"
MANIFEST = "fixture/requirements.txt"
SAFE_PACKAGE = "requests==2.32.5\n"
OLD_PACKAGE = "requests==2.19.1\n"
DB_PATH = Path("/tmp/trivy-cache/db")


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_PINNED_TRIVY_DB") == "1",
    "Requires immutable OCI Trivy-DB snapshot in no-network CI container",
)
class RealTrivyFrozenPublicDatabaseTests(unittest.TestCase):
    def test_original_snapshot_and_attribution_with_actual_frozen_advisory_db(self):
        real = _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
        self.assertEqual(real.name, "trivy")
        version = subprocess.run(
            [str(real), "--version"], capture_output=True,
            text=True, timeout=20, check=True,
        )
        self.assertIn(TRIVY_VERSION, version.stdout + version.stderr)
        db = DB_PATH / "trivy.db"
        metadata = DB_PATH / "metadata.json"
        self.assertTrue(db.is_file(), "The frozen DB must be mounted, not downloaded in scan")
        self.assertTrue(metadata.is_file())
        self.assertGreater(db.stat().st_size, 100_000)
        meta = json.loads(metadata.read_text(encoding="utf-8"))
        self.assertIsInstance(meta, dict)
        self.assertIn("Version", meta)
        print(
            "Frozen candidate Trivy-DB:",
            {"db_bytes": db.stat().st_size, "metadata": meta},
        )
        with tempfile.TemporaryDirectory(prefix="arno_trivy_frozen_") as td:
            root = Path(td)
            sources = []
            for side, body in (("base", SAFE_PACKAGE), ("head", OLD_PACKAGE)):
                location = root / side
                (location / "fixture").mkdir(parents=True)
                (location / MANIFEST).write_text(body, encoding="utf-8")
                sources.append((side, location, body))
            shell = _original_shell()
            calls = []

            def restricted_cmd(cmd, cwd=None, timeout=None, env=None):
                if not isinstance(cmd, list) or cwd is not None or env is not None:
                    raise AssertionError("Only the exact original Trivy CLI is allowed")
                for side, location, body in sources:
                    expected = [
                        "trivy", "filesystem", "--scanners", "vuln",
                        "--pkg-types", "library", "--include-dev-deps",
                        "--offline-scan", "--format", "json",
                        "--no-progress", "--exit-code", "0",
                        str(location),
                    ]
                    if cmd == expected:
                        if (location / MANIFEST).read_text(encoding="utf-8") != body:
                            raise AssertionError("The synthetic manifest was modified")
                        if not db.is_file() or not metadata.is_file():
                            raise AssertionError("The frozen local Trivy DB disappeared")
                        _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
                        calls.append(side)
                        return shell(
                            cmd, timeout=min(timeout or 120, 120),
                        )
                raise AssertionError("Non-fixture Trivy command rejected")

            archived = _load_original_trivy(restricted_cmd)
            scan = archived.__globals__["_scan_snapshot"]
            with mock.patch.dict(os.environ, {
                "TRIVY_CACHE_DIR": "/tmp/trivy-cache",
                "TRIVY_SKIP_DB_UPDATE": "true",
                "TRIVY_SKIP_JAVA_DB_UPDATE": "true",
                "TRIVY_SKIP_VERSION_CHECK": "true",
            }):
                baseline, base_meta = scan(
                    sources[0][1], "synthetic-base", [MANIFEST],
                    TRIVY_VERSION, timeout_seconds=120,
                )
                head, head_meta = scan(
                    sources[1][1], "synthetic-head", [MANIFEST],
                    TRIVY_VERSION, timeout_seconds=120,
                )
            self.assertEqual(calls, ["base", "head"])
            self.assertEqual(base_meta["status"], "ok", base_meta)
            self.assertEqual(head_meta["status"], "ok", head_meta)
            self.assertTrue(head, (head_meta, head))
            matching = [
                finding for finding in head
                if (finding.get("package") or "").lower() == "requests"
            ]
            self.assertTrue(matching, (head_meta, head))
            introduced = archived.__globals__["_introduced_findings"](
                baseline, head, [MANIFEST]
            )
            self.assertTrue(introduced, (baseline, head, head_meta))
            self.assertTrue(all(x["introduced"] == 1 for x in introduced))
            self.assertTrue(all(x["diff_linked"] for x in introduced))
            self.assertTrue(all(
                json.loads(x["evidence"])["pr_attributable"]
                if isinstance(x["evidence"], str) else x["evidence"]["pr_attributable"]
                for x in introduced
            ))
            self.assertTrue(all(x.get("vuln_id") for x in introduced))


if __name__ == "__main__":
    unittest.main()
