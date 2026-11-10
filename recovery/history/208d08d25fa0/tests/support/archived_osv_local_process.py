"""Run SHA-pinned original OSV snapshot driver on local Git and fake OSV CLI.

TEST ONLY: original AST, original shell, synthetic two-commit repository,
allowlisted command arguments, and no network. Fake osv-scanner is NOT OSV.
Never use with Wits data, original research DBs or real repository URLs.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import subprocess
import tempfile
from typing import Any
from unittest import mock

from src.scanners.dependency_diff import is_dependency_file
from tests.support.archived_dependency_snapshot_pure import OSV_PATH, OSV_SHA256
from tests.support.archived_gitleaks_process import (
    SHELL_FUNCTIONS, SHELL_PATH, SHELL_SHA256, _exact_defs,
)

REPO_URL = "https://example.invalid/fixture/osv-snapshots"
MANIFEST = "fixture/pyproject.toml"
COMPANION = "fixture/poetry.lock"
BASE_CONTENT = 'synthetic_lib = "2.0"\n'
HEAD_CONTENT = 'synthetic_lib = "1.0"\n'
COMPANION_CONTENT = "SYNTHETIC_LOCK_FIXTURE_ONLY\n"
DIFF = '@@ -1 +1 @@\n-synthetic_lib = "2.0"\n+synthetic_lib = "1.0"\n'
ADVISORY_ID = "OSV-SYNTHETIC-0001"

OSV_FUNCTIONS = (
    "_dependency_state_lines", "_write_dependency_delta_files", "_scan_dir",
    "_advisory_ids", "_finding_key", "_normalise_dependency_path",
    "_dependency_paths_for_snapshot", "_rename_aliases",
    "_dependency_ancestor_directories", "_discover_dependency_companions",
    "_materialize_git_snapshot", "_snapshot_finding_key", "_snapshot_status",
    "scan_dependency_snapshots",
)
STUB = r'''#!/usr/bin/env python3
"""Emit deterministic synthetic OSV JSON, not advisory-engine results."""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
expected = [
    "scan", "source", "--recursive", "--no-ignore",
    "--allow-no-lockfiles", "--format", "json",
]
if len(args) != len(expected) + 1 or args[:-1] != expected:
    print("Unexpected OSV command", file=sys.stderr)
    sys.exit(7)
root = Path(args[-1]).resolve()
manifest = root / "fixture" / "pyproject.toml"
companion = root / "fixture" / "poetry.lock"
if not manifest.is_file() or not companion.is_file():
    print("Synthetic manifest/companion missing", file=sys.stderr)
    sys.exit(8)
content = manifest.read_text(encoding="utf-8")
lock = companion.read_text(encoding="utf-8")
if content not in {'synthetic_lib = "1.0"\n', 'synthetic_lib = "2.0"\n'} or lock != "SYNTHETIC_LOCK_FIXTURE_ONLY\n":
    print("Unexpected source data", file=sys.stderr)
    sys.exit(9)
vulns = []
if content == 'synthetic_lib = "1.0"\n':
    vulns = [{
        "id": "OSV-SYNTHETIC-0001", "aliases": ["GHSA-SYNTHETIC-0001"],
        "summary": "Synthetic-only advisory; no real security finding",
    }]
if content == 'synthetic_lib = "1.0"\n':
    mode = os.environ.get("ARNO_OSV_FAKE_MODE", "ok")
    if mode == "head-malformed-success":
        print("not valid JSON")
        sys.exit(0)
    if mode not in ("ok", "head-extraction-failed"):
        print("unapproved synthetic OSV failure mode", file=sys.stderr)
        sys.exit(10)
report = {"results": [{
    "source": {"path": str(manifest)},
    "packages": [{
        "package": {"name": "synthetic_lib", "version": "1.0" if vulns else "2.0"},
        "vulnerabilities": vulns,
    }],
}]}
print(json.dumps(report))
if content == 'synthetic_lib = "1.0"\n' and os.environ.get("ARNO_OSV_FAKE_MODE") == "head-extraction-failed":
    print("Could not extract packages from synthetic fixture", file=sys.stderr)
    sys.exit(9)
sys.exit(1 if vulns else 0)
'''


def _load_original_osv(run_cmd):
    original = OSV_PATH.read_bytes()
    if hashlib.sha256(original).hexdigest() != OSV_SHA256:
        raise ValueError("Archived OSV source hash mismatch")
    tree = ast.parse(original, filename=str(OSV_PATH))
    defs = {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in OSV_FUNCTIONS
    }
    if set(defs) != set(OSV_FUNCTIONS) or any(d.decorator_list for d in defs.values()):
        raise ValueError("Original OSV function inventory changed")
    constants = [node for node in tree.body
                 if isinstance(node, ast.Assign)
                 and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id == "DEPENDENCY_COMPANION_GROUPS"]
    if len(constants) != 1:
        raise ValueError("Original OSV companion group constant missing")
    groups = ast.literal_eval(constants[0].value)
    shell_code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    shell_scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "os": os, "subprocess": subprocess, "signal": signal, "json": json,
    }
    exec(shell_code, shell_scope, shell_scope)
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Any": Any, "Path": Path, "PurePosixPath": PurePosixPath,
        "json": json, "shutil": shutil, "tempfile": tempfile,
        "is_dependency_file": is_dependency_file,
        "run_cmd": run_cmd,
        "parse_json_maybe": shell_scope["parse_json_maybe"],
        "DEPENDENCY_COMPANION_GROUPS": groups,
    }
    compiled = compile(
        ast.fix_missing_locations(ast.Module(
            body=[defs[name] for name in OSV_FUNCTIONS], type_ignores=[],
        )),
        str(OSV_PATH), "exec", flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    exec(compiled, scope, scope)
    return scope["scan_dependency_snapshots"]


class LocalOSVReplay:
    """Only a two-commit synthetic repo and deterministic synthetic OSV outputs."""

    def __init__(self):
        self.temp = None
        self.calls = []
        self.clone_dir = None

    @staticmethod
    def _git(*args, cwd):
        completed = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=30, check=True,
        )
        return completed.stdout.strip()

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arno_osv_replay_")
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self._git("init", "--quiet", cwd=self.source)
        manifest = self.source / MANIFEST
        manifest.parent.mkdir(parents=True)
        manifest.write_text(BASE_CONTENT, encoding="utf-8")
        companion = self.source / COMPANION
        companion.write_text(COMPANION_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic base manifests",
            cwd=self.source,
        )
        self.base_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        manifest.write_text(HEAD_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic head downgrade",
            cwd=self.source,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.binary = self.bin / "osv-scanner"
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
        self.original_osv = _load_original_osv(self._restricted_cmd)
        return self

    def __exit__(self, *exc):
        if self.temp is not None:
            self.temp.cleanup()
            self.temp = None

    @staticmethod
    def files():
        return [{
            "filename": MANIFEST, "category": "dependency",
            "status": "modified", "patch": DIFF,
            "additions": 1, "deletions": 1,
        }]

    def _restricted_cmd(self, cmd, cwd=None, timeout=None, env=None):
        if (
            not isinstance(cmd, list) or not cmd or env is not None
            or any(not isinstance(arg, str) for arg in cmd)
        ):
            raise ValueError("Unexpected archived OSV subprocess request")
        working = Path(cwd).resolve() if cwd is not None else None
        if (
            len(cmd) == 7
            and cmd[:6] == ["git", "clone", "--depth", "1", "--no-checkout", REPO_URL]
            and working is not None
        ):
            self.clone_dir = Path(cmd[6]).resolve()
            if (
                self.clone_dir != working / "repo"
                or self.clone_dir.parent == self.root
                or not str(working).startswith(
                    str(Path(tempfile.gettempdir()).resolve()) + os.sep
                )
            ):
                raise ValueError("Disallowed original OSV Git clone destination")
            command = cmd[:5] + ["file://" + str(self.source), cmd[6]]
        elif (
            len(cmd) == 6 and cmd[:4] == ["git", "fetch", "--depth", "1"]
            and cmd[4] == "origin" and cmd[5] in (self.base_sha, self.head_sha)
            and working == self.clone_dir
        ):
            command = cmd
        elif (
            len(cmd) == 5 and cmd[:3] == ["git", "ls-tree", "-r"]
            and cmd[3] == "--name-only"
            and cmd[4] in (self.base_sha, self.head_sha)
            and working == self.clone_dir
        ):
            command = cmd
        elif (
            len(cmd) == 3 and cmd[:2] == ["git", "show"]
            and working == self.clone_dir
            and cmd[2] in {
                f"{sha}:{path}"
                for sha in (self.base_sha, self.head_sha)
                for path in (MANIFEST, COMPANION)
            }
        ):
            command = cmd
        elif (
            len(cmd) == 9
            and cmd[:8] == [
                "osv-scanner", "scan", "source", "--recursive",
                "--no-ignore", "--allow-no-lockfiles", "--format", "json"
            ]
            and cwd is None
        ):
            root = Path(cmd[8]).resolve()
            if self.clone_dir is None or root not in (
                self.clone_dir.parent / "base", self.clone_dir.parent / "head"
            ):
                raise ValueError("Disallowed OSV snapshot directory")
            if Path(shutil.which("osv-scanner") or "").resolve() != self.binary:
                raise ValueError("Unapproved OSV CLI selected")
            command = cmd
        else:
            raise ValueError(f"Disallowed original OSV subprocess: {cmd[0]}")
        self.calls.append((cmd[0], tuple(cmd[1:])))
        return self.original_shell(command, cwd=cwd, timeout=timeout)

    def scan(self, repo_url, base_sha, head_sha, files, *, timeout_seconds=120):
        if (
            self.temp is None or repo_url != REPO_URL
            or base_sha != self.base_sha or head_sha != self.head_sha
            or files != self.files()
        ):
            raise ValueError("Only exact synthetic OSV snapshot input allowed")
        with mock.patch.dict(os.environ, {
            "PATH": str(self.binary.parent) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
            "OSV_SCANNER_TELEMETRY": "off",
        }):
            if Path(shutil.which("osv-scanner") or "").resolve() != self.binary:
                raise ValueError("Synthetic OSV executable failed PATH isolation")
            return self.original_osv(
                repo_url, base_sha, head_sha, files,
                timeout_seconds=timeout_seconds,
            )
