"""Execute the exact archived Trivy snapshot driver against a strict local CLI stub.

TEST ONLY. The archived module is hash-checked and selected AST functions are
compiled, never imported as a module. All git commands are allowlisted, and
the only original remote clone command is rewritten to a self-generated local
file:// fixture. The Trivy executable is a tiny deterministic fake, NOT Trivy.
No network target, historical DB, user repo or Wits paths can enter.
"""
from __future__ import annotations

import __future__
import ast
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from typing import Any
from unittest import mock

from src.scanners.dependency_diff import is_dependency_file
from tests.support.archived_dependency_snapshot_pure import TRIVY_PATH, TRIVY_SHA256
from tests.support.archived_gitleaks_process import (
    SHELL_FUNCTIONS, SHELL_PATH, SHELL_SHA256, _exact_defs,
)

REPO_URL = "https://example.invalid/fixture/trivy-snapshots"
FILENAME = "fixture/requirements.txt"
BASE_CONTENT = "synthetic-lib==2.0\n"
HEAD_CONTENT = "synthetic-lib==1.0\n"
DIFF = "@@ -1 +1 @@\n-synthetic-lib==2.0\n+synthetic-lib==1.0\n"
ADVISORY_ID = "SYNTHETIC-TRIVY-0001"
TRIVY_FUNCTIONS = (
    "_dependency_paths", "_normalise_target", "_advisory_ids",
    "_finding_locator", "_parse_report", "_snapshot_delta_findings",
    "_trivy_json_dict", "_trivy_normalise_path", "_trivy_paths_equal",
    "_trivy_finding_target", "_trivy_target_changed_by_pr",
    "_introduced_findings", "_attach_trivy_package_locations",
    "_command_failure_meta", "_scan_snapshot", "_combined_status",
    "scan_dependency_snapshots_with_trivy",
)
STUB = r'''#!/usr/bin/env python3
"""Synthetic Trivy-shaped JSON; NOT a vulnerability engine."""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("Version: synthetic-trivy-stub 0.0.0")
    sys.exit(0)
expected = [
    "filesystem", "--scanners", "vuln", "--pkg-types", "library",
    "--include-dev-deps", "--offline-scan", "--format", "json",
    "--no-progress", "--exit-code", "0",
]
if args[:-1] != expected or len(args) != len(expected) + 1:
    print("disallowed synthetic Trivy arguments", file=sys.stderr)
    sys.exit(4)
root = Path(args[-1]).resolve()
target = root / "fixture" / "requirements.txt"
if not target.is_file():
    print("expected synthetic dependency manifest missing", file=sys.stderr)
    sys.exit(5)
content = target.read_text(encoding="utf-8")
if content not in {"synthetic-lib==1.0\n", "synthetic-lib==2.0\n"}:
    print("unexpected non-synthetic manifest", file=sys.stderr)
    sys.exit(6)
if content == "synthetic-lib==1.0\n":
    mode = os.environ.get("ARNO_TRIVY_FAKE_MODE", "ok")
    if mode == "head-malformed-json":
        print("NOT VALID JSON")
        sys.exit(0)
    if mode not in ("ok", "head-structured-nonzero"):
        print("unapproved synthetic failure mode", file=sys.stderr)
        sys.exit(10)
vulns = []
if content == "synthetic-lib==1.0\n":
    vulns.append({
        "VulnerabilityID": "SYNTHETIC-TRIVY-0001",
        "PkgName": "synthetic-lib", "InstalledVersion": "1.0",
        "FixedVersion": "2.0", "Severity": "HIGH",
        "CweIDs": ["CWE-000"],
        "Title": "Harmless fabricated advisory; no live CVE or credential",
        "Aliases": ["SYNTHETIC-ALIAS-0001"],
    })
print(json.dumps({"SchemaVersion": 2, "Results": [{
    "Target": "fixture/requirements.txt", "Class": "lang-pkgs",
    "Type": "pip", "Vulnerabilities": vulns,
    "Packages": [{
        "Name": "synthetic-lib", "Version": "1.0" if vulns else "2.0",
        "Locations": [{"StartLine": 1, "EndLine": 1}],
    }],
}]}))
if content == "synthetic-lib==1.0\n" and os.environ.get("ARNO_TRIVY_FAKE_MODE") == "head-structured-nonzero":
    print("Synthetic Trivy nonzero exit despite structured JSON", file=sys.stderr)
    sys.exit(13)
'''


def _load_original_trivy(run_cmd):
    raw = TRIVY_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != TRIVY_SHA256:
        raise ValueError("Historical Trivy source SHA-256 mismatch")
    tree = ast.parse(raw, filename=str(TRIVY_PATH))
    methods = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in TRIVY_FUNCTIONS
    }
    if set(methods) != set(TRIVY_FUNCTIONS):
        raise ValueError("Trivy archived function inventory differs")
    if any(methods[name].decorator_list for name in methods):
        raise ValueError("Trivy decorated function unexpectedly selected")
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Any": Any, "Path": Path, "json": json,
        "shutil": shutil, "tempfile": tempfile,
        "defaultdict": defaultdict, "is_dependency_file": is_dependency_file,
        "run_cmd": run_cmd,
    }
    shell_code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    shell_scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "os": os, "subprocess": subprocess, "signal": signal, "json": json,
    }
    exec(shell_code, shell_scope, shell_scope)
    scope["parse_json_maybe"] = shell_scope["parse_json_maybe"]
    src = compile(
        ast.fix_missing_locations(ast.Module(
            body=[methods[name] for name in TRIVY_FUNCTIONS], type_ignores=[],
        )),
        str(TRIVY_PATH), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    )
    exec(src, scope, scope)
    return scope["scan_dependency_snapshots_with_trivy"]


class LocalTrivyReplay:
    """One repository, two synthetic commits, one local fake Trivy binary."""

    def __init__(self):
        self.temp = None
        self.calls = []
        self.checkout_dir = None

    @staticmethod
    def _git(*args, cwd):
        p = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True,
            text=True, timeout=25, check=True,
        )
        return p.stdout.strip()

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arno_trivy_replay_")
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self._git("init", "--quiet", cwd=self.source)
        manifest = self.source / FILENAME
        manifest.parent.mkdir(parents=True)
        manifest.write_text(BASE_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic base",
            cwd=self.source,
        )
        self.base_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        manifest.write_text(HEAD_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic downgrade",
            cwd=self.source,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.binary = self.bin / "trivy"
        compile(STUB, "<isolated-synthetic-stub>", "exec")
        self.binary.write_text(STUB, encoding="utf-8")
        self.binary.chmod(0o700)
        shell_code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
        scope = {
            "__builtins__": __builtins__, "__name__": __name__,
            "os": os, "subprocess": subprocess, "signal": signal, "json": json,
        }
        exec(shell_code, scope, scope)
        self.original_shell = scope["run_cmd"]
        self.original_trivy = _load_original_trivy(self._restricted_cmd)
        return self

    def __exit__(self, *exc):
        if self.temp is not None:
            self.temp.cleanup()
            self.temp = None

    @staticmethod
    def files():
        return [{
            "filename": FILENAME, "category": "dependency",
            "status": "modified", "patch": DIFF,
            "additions": 1, "deletions": 1,
        }]

    def _restricted_cmd(self, cmd, cwd=None, timeout=None, env=None):
        if (
            not isinstance(cmd, list) or not cmd or env is not None
            or any(not isinstance(x, str) for x in cmd)
        ):
            raise ValueError("Unapproved archived command")
        cwd_path = Path(cwd).resolve() if cwd is not None else None
        if cmd == ["trivy", "--version"] and cwd is None:
            if Path(shutil.which("trivy") or "").resolve() != self.binary:
                raise ValueError("Unexpected Trivy executable")
            actual_cmd = cmd
        elif (
            cmd[:7] == ["git", "clone", "--depth", "1",
                        "--filter=blob:none", "--no-checkout", REPO_URL]
            and len(cmd) == 8 and cwd is None
        ):
            self.checkout_dir = Path(cmd[7]).resolve()
            if self.checkout_dir.name != "repo" or self.checkout_dir == self.source:
                raise ValueError("Unexpected archived clone destination")
            if self.checkout_dir.parent == self.root or self.checkout_dir.parent == self.source:
                raise ValueError("Source fixture must not be modified")
            if not str(self.checkout_dir.parent).startswith(str(Path(tempfile.gettempdir()).resolve()) + os.sep):
                raise ValueError("Only a disposable tmp worktree is allowed")
            actual_cmd = cmd[:6] + ["file://" + str(self.source), cmd[7]]
        elif (
            len(cmd) == 6 and cmd[:4] == ["git", "fetch", "--depth", "1"]
            and cmd[4] == "origin"
            and cmd[5] in (self.base_sha, self.head_sha)
            and cwd_path == self.checkout_dir
        ):
            actual_cmd = cmd
        elif (
            len(cmd) == 7 and cmd[:5] == ["git", "worktree", "add", "--detach", "--force"]
            and cmd[6] in (self.base_sha, self.head_sha)
            and cwd_path == self.checkout_dir
        ):
            dest = Path(cmd[5]).resolve()
            side = "base" if cmd[6] == self.base_sha else "head"
            if dest != self.checkout_dir.parent / side:
                raise ValueError("Incorrect base/head worktree")
            actual_cmd = cmd
        elif (
            len(cmd) == 14 and cmd[:13] == [
                "trivy", "filesystem", "--scanners", "vuln",
                "--pkg-types", "library", "--include-dev-deps",
                "--offline-scan", "--format", "json",
                "--no-progress", "--exit-code", "0",
            ]
            and cwd is None
        ):
            target = Path(cmd[13]).resolve()
            if self.checkout_dir is None or target not in (
                self.checkout_dir.parent / "base",
                self.checkout_dir.parent / "head",
            ):
                raise ValueError("Unexpected Trivy target directory")
            if Path(shutil.which("trivy") or "").resolve() != self.binary:
                raise ValueError("Unexpected Trivy executable")
            actual_cmd = cmd
        else:
            raise ValueError("Unapproved archived shell command: " + cmd[0])
        self.calls.append((cmd[0], tuple(cmd[1:])))
        return self.original_shell(actual_cmd, cwd=cwd, timeout=timeout)

    def scan(self, repo_url, base_sha, head_sha, files, *, timeout_seconds=120):
        if (
            self.temp is None or repo_url != REPO_URL
            or base_sha != self.base_sha or head_sha != self.head_sha
            or files != self.files()
        ):
            raise ValueError("Only synthetic Trivy snapshot inputs allowed")
        with mock.patch.dict(os.environ, {
            "PATH": str(self.binary.parent) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
            "TRIVY_DISABLE_VEX_NOTICE": "true",
        }):
            if Path(shutil.which("trivy") or "").resolve() != self.binary:
                raise ValueError("Local Trivy stub not on PATH")
            return self.original_trivy(
                repo_url, base_sha, head_sha, files,
                timeout_seconds=timeout_seconds,
            )
