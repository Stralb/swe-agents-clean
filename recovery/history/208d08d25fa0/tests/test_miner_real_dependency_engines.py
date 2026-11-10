"""Real checksum-verified OSV and Trivy CLI integration on synthetic offline data.

Runs only in .github/workflows/synthetic-dependency-engines.yml, inside a
no-network, non-root, read-only sandbox. Both exact original archived parsing
functions are selected by SHA-verified AST; historical modules are never
imported. The OSV advisory DB is *synthetic*, not an upstream database.
Trivy intentionally has NO vulnerability database, and failure must be explicit.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import unittest
from unittest import mock
from zipfile import ZIP_STORED, ZipFile

from tests.support.archived_gitleaks_process import (
    SHELL_FUNCTIONS, SHELL_PATH, SHELL_SHA256, _exact_defs,
)
from tests.support.archived_osv_local_process import _load_original_osv
from tests.support.archived_trivy_local_process import _load_original_trivy

OSV_SHA256 = "ca69b3d3cd08f889a49dc0a383122f71cc528b83803671df5fd874d97485b108"
TRIVY_VERSION = "0.76.1"
OSV_VERSION = "2.6.0"
PACKAGE = "arno-synthetic-fixture-lib"
ADVISORY = "OSV-ARNO-SYNTHETIC-0001"
REQUIREMENTS = PACKAGE + "==1.0.0\n"

# No real advisory, vulnerability, or dependency is checked into this repo.
SYNTHETIC_ADVISORY = {
    "schema_version": "1.6.0",
    "id": ADVISORY,
    "published": "2026-01-01T00:00:00Z",
    "modified": "2026-01-01T00:00:00Z",
    "summary": "Synthetic test advisory; never a genuine vulnerability",
    "details": "Fabricated scanner integration test only",
    "affected": [{
        "package": {"ecosystem": "PyPI", "name": PACKAGE},
        "ranges": [{
            "type": "ECOSYSTEM",
            "events": [
                {"introduced": "0"},
                {"fixed": "2.0.0"},
            ],
        }],
    }],
}


def _original_shell():
    code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "json": json, "os": os, "signal": signal,
        "subprocess": subprocess,
    }
    exec(code, scope, scope)
    return scope["run_cmd"]


def _allowlisted_binary(name: str, variable: str, digest: str | None):
    path = Path(os.environ[variable]).resolve()
    if path.name != name or not path.is_file():
        raise ValueError("Expected only the verified scanner binary")
    if Path(shutil.which(name) or "").resolve() != path:
        raise ValueError("Scanner executable on PATH does not match the verified binary")
    if digest is not None:
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h != digest:
            raise ValueError("Scanner binary digest mismatch")
    return path


@unittest.skipUnless(
    os.environ.get("ARNO_RUN_REAL_DEPENDENCY_ENGINES") == "1",
    "Use separate checksum-verified, no-network dependency-scanner job",
)
class ArchivedRealDependencyEngineSmoke(unittest.TestCase):
    def test_offline_real_osv_uses_original_report_parser_on_synthetic_local_db(self):
        real = _allowlisted_binary("osv-scanner", "ARNO_OSV_BINARY", OSV_SHA256)
        version = subprocess.run(
            [str(real), "--version"], capture_output=True, text=True,
            timeout=25, check=True,
        )
        self.assertIn(OSV_VERSION, version.stdout + version.stderr)
        with tempfile.TemporaryDirectory(prefix="arno_real_osv_offline_") as td:
            work = Path(td)
            target = work / "source"
            target.mkdir()
            req = target / "requirements.txt"
            req.write_text(REQUIREMENTS, encoding="utf-8")
            db = work / "db"
            # v2.5+ migrated offline matching to osv-scalibr. The old
            # osv-scanner prefix is retained too for explicit compatibility.
            # None of these ZIPs contains a real advisory.
            zip_paths = [
                db / prefix / "PyPI" / "all.zip"
                for prefix in ("osv-scalibr", "osv-scanner")
            ]
            data = json.dumps(SYNTHETIC_ADVISORY, sort_keys=True, separators=(",", ":"))
            for zip_path in zip_paths:
                zip_path.parent.mkdir(parents=True)
                with ZipFile(zip_path, "w", compression=ZIP_STORED) as archive:
                    archive.writestr(ADVISORY + ".json", data)
            self.assertEqual(req.read_text(), REQUIREMENTS)
            for zip_path in zip_paths:
                with ZipFile(zip_path) as archive:
                    loaded = json.loads(archive.read(ADVISORY + ".json"))
                self.assertEqual(loaded, SYNTHETIC_ADVISORY)
            shell = _original_shell()
            calls = []

            def restricted_cmd(cmd, cwd=None, timeout=None, env=None):
                expected = [
                    "osv-scanner", "scan", "source", "--recursive", "--no-ignore",
                    "--allow-no-lockfiles", "--format", "json", str(target),
                ]
                if cmd != expected or cwd is not None or env is not None:
                    raise AssertionError("Non-fixture original OSV command rejected")
                if not all(path.is_file() for path in zip_paths) or req.read_text() != REQUIREMENTS:
                    raise AssertionError("Synthetic advisory or manifest changed")
                _allowlisted_binary("osv-scanner", "ARNO_OSV_BINARY", OSV_SHA256)
                # Safety-only CLI injection: archived _scan_dir is UNMODIFIED.
                # The production-original invocation did NOT have these flags.
                command = cmd[:-1] + [
                    "--offline",
                    "--local-db-path", str(db),
                    "--no-resolve",
                    str(target),
                ]
                calls.append(command)
                with mock.patch.dict(os.environ, {
                    "OSV_SCALIBR_LOCAL_DB_CACHE_DIRECTORY": str(db),
                    "OSV_SCANNER_LOCAL_DB_CACHE_DIRECTORY": str(db),
                }):
                    return shell(command, cwd=None, timeout=min(timeout or 90, 90))

            original_driver = _load_original_osv(restricted_cmd)
            original_scan = original_driver.__globals__["_scan_dir"]
            findings, meta = original_scan(target, timeout_seconds=90)
            self.assertEqual(len(calls), 1)
            self.assertEqual(meta["status"], "ok", (meta, findings))
            self.assertTrue(findings, (meta, findings))
            synthetic = [x for x in findings if x.get("vuln_id") == ADVISORY]
            self.assertEqual(len(synthetic), 1, (meta, findings))
            self.assertEqual(synthetic[0]["package"], PACKAGE)
            self.assertEqual(synthetic[0]["version"], "1.0.0")
            self.assertIn("synthetic", synthetic[0]["description"].lower())

    def test_trivy_actual_binary_with_no_database_must_fail_closed(self):
        real = _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
        version = subprocess.run(
            [str(real), "--version"], capture_output=True, text=True,
            timeout=25, check=True,
        )
        self.assertIn(TRIVY_VERSION, version.stdout + version.stderr)
        with tempfile.TemporaryDirectory(prefix="arno_real_trivy_no_db_") as td:
            base = Path(td)
            root = base / "source"
            (root / "fixture").mkdir(parents=True)
            (root / "fixture" / "requirements.txt").write_text(
                REQUIREMENTS, encoding="utf-8"
            )
            cache = base / "empty-cache"
            cache.mkdir()
            shell = _original_shell()
            calls = []

            def restricted_cmd(cmd, cwd=None, timeout=None, env=None):
                expected = [
                    "trivy", "filesystem", "--scanners", "vuln",
                    "--pkg-types", "library", "--include-dev-deps",
                    "--offline-scan", "--format", "json",
                    "--no-progress", "--exit-code", "0", str(root),
                ]
                if cmd != expected or cwd is not None or env is not None:
                    raise AssertionError("Non-fixture original Trivy command rejected")
                _allowlisted_binary("trivy", "ARNO_TRIVY_BINARY", None)
                if (root / "fixture" / "requirements.txt").read_text() != REQUIREMENTS:
                    raise AssertionError("Unexpected Trivy fixture manifest")
                calls.append(cmd)
                with mock.patch.dict(os.environ, {
                    "TRIVY_CACHE_DIR": str(cache),
                    "TRIVY_SKIP_DB_UPDATE": "true",
                    "TRIVY_SKIP_JAVA_DB_UPDATE": "true",
                    "TRIVY_SKIP_VERSION_CHECK": "true",
                }):
                    return shell(cmd, cwd=None, timeout=min(timeout or 90, 90))

            driver = _load_original_trivy(restricted_cmd)
            scan = driver.__globals__["_scan_snapshot"]
            findings, meta = scan(
                root, "synthetic-head", ["fixture/requirements.txt"],
                TRIVY_VERSION, timeout_seconds=90,
            )
            self.assertEqual(len(calls), 1)
            self.assertEqual(findings, [], (meta, findings))
            self.assertIn(
                meta["status"], ("error", "parse_failed"),
                "Missing genuine advisory DB must never count as clean",
            )
            report = json.loads(meta["stdout"])
            self.assertIsNone(report["report"])
            self.assertEqual(report["sha"], "synthetic-head")


if __name__ == "__main__":
    unittest.main()
