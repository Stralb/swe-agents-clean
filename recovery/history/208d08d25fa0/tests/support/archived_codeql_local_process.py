"""Exact historic CodeQL Git clone/database/SARIF runner with synthetic fake CLI.

SAFETY: SHA verifies archived source and AST-selects fixed functions (never
imports the original module). Commands are allowlisted, clone URL is redirected
to a generated local file:// Git repo, and only fabricated Python is scanned.
The temporary executable named "codeql" is NOT the real CodeQL engine.
"""
from __future__ import annotations

import __future__
import ast
from contextlib import contextmanager
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

from tests.support.archived_codeql_attribution_contract import (
    SOURCE_PATH, SOURCE_SHA256,
)
from tests.support.archived_gitleaks_process import (
    SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS, _exact_defs,
)

REPO_URL = "https://example.invalid/fixture/codeql-snapshots"
FILENAME = "src/app.py"
BASE_CONTENT = "def run():\n    return 0\n"
HEAD_CONTENT = (
    "def run():\n    return 0\n\n\n"
    "def introduced_sink():\n    return 'synthetic'\n"
)
PATCH = (
    "@@ -1,2 +1,6 @@\n"
    " def run():\n"
    "     return 0\n"
    "+\n"
    "+\n"
    "+def introduced_sink():\n"
    "+    return 'synthetic'\n"
)
RULE = "arno/synthetic-codeql-warning"
SUITE = "codeql/python-queries:codeql-suites/python-security-extended.qls"
SOURCE_FUNCTIONS = (
    "_norm_path", "_codeql_tmp_parent", "_codeql_tempdir",
    "_codeql_preflight", "_sarif_location_tuple", "_extract_all_locations",
    "_cmd_error_meta", "_command_timed_out", "_codeql_no_source_seen",
    "_timeout_meta", "_no_source_meta", "scan_snapshot_with_codeql",
)
STUB = r'''#!/usr/bin/env python3
"""Deterministic fake CodeQL CLI, cannot scan external repositories."""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("Synthetic CodeQL stub 0.0.0")
    sys.exit(0)

if args[:2] == ["database", "create"] and len(args) == 8:
    db = Path(args[2]).resolve()
    expect = [
        "--language=python", "--source-root=",
        "--ram=4096", "--threads=1", "--build-mode=none",
    ]
    if args[3] != expect[0] or not args[4].startswith(expect[1]) or args[5:] != expect[2:]:
        print("Unexpected database create arguments", file=sys.stderr)
        sys.exit(3)
    source = Path(args[4].split("=", 1)[1]).resolve()
    if db.parent != source.parent or db.name != "codeql-db" or source.name != "repo":
        print("Synthetic CodeQL source/db directory mismatch", file=sys.stderr)
        sys.exit(4)
    file = source / "src/app.py"
    base = "def run():\n    return 0\n"
    head = base + "\n\ndef introduced_sink():\n    return 'synthetic'\n"
    if file.read_text(encoding="utf-8") not in (base, head):
        print("Unapproved synthetic CodeQL source", file=sys.stderr)
        sys.exit(5)
    if os.environ.get("ARNO_FAKE_CODEQL_MODE") == "head-no-source" and file.read_text() == head:
        print("No source code was seen during extraction", file=sys.stderr)
        sys.exit(32)
    db.mkdir()
    (db / "synthetic-head.txt").write_text(
        "head" if file.read_text() == head else "base"
    )
    print("Synthetic database created")
    sys.exit(0)

if args[:2] == ["database", "analyze"] and len(args) == 8:
    db = Path(args[2]).resolve()
    output = args[5]
    if (args[3] != "codeql/python-queries:codeql-suites/python-security-extended.qls"
        or args[4] != "--format=sarif-latest"
        or not output.startswith("--output=")
        or args[6:] != ["--ram=4096", "--threads=1"]):
        print("Unexpected CodeQL analyze arguments", file=sys.stderr)
        sys.exit(8)
    dest = Path(output.split("=", 1)[1]).resolve()
    if dest.parent != db.parent or dest.name != "results.sarif":
        print("Unapproved SARIF destination", file=sys.stderr)
        sys.exit(9)
    if db.name != "codeql-db":
        print("Invalid synthetic CodeQL database", file=sys.stderr)
        sys.exit(10)
    status = (db / "synthetic-head.txt").read_text()
    findings = [] if status == "base" else [{
        "ruleId": "arno/synthetic-codeql-warning",
        "level": "warning",
        "message": {"text": "Fabricated CodeQL diagnostic, not a real vulnerability"},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": "src/app.py"},
                "region": {"startLine": 5},
            },
        }],
    }]
    report = {
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "Synthetic CodeQL fixture",
                "rules": [{
                    "id": "arno/synthetic-codeql-warning",
                    "properties": {
                        "tags": ["external/cwe/cwe-078"],
                        "problem.severity": "warning",
                    },
                }],
            }},
            "results": findings,
        }],
    }
    if (
        status == "head"
        and os.environ.get("ARNO_FAKE_CODEQL_MODE") == "head-malformed-sarif"
    ):
        dest.write_text("NOT VALID SARIF JSON", encoding="utf-8")
    else:
        dest.write_text(json.dumps(report))
    print("Synthetic SARIF report written")
    sys.exit(0)

print("Disallowed synthetic CodeQL invocation", file=sys.stderr)
sys.exit(11)
'''


def _exact_original_codeql(run_cmd):
    data = SOURCE_PATH.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError("Historical CodeQL source hash differs")
    tree = ast.parse(data, filename=str(SOURCE_PATH))
    defs = {
        n.name: n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in SOURCE_FUNCTIONS
    }
    if set(defs) != set(SOURCE_FUNCTIONS):
        raise ValueError("Unapproved original CodeQL function inventory")
    decorators = {
        n.name: [
            deco.id for deco in n.decorator_list if isinstance(deco, ast.Name)
        ] for n in defs.values()
    }
    if decorators["_codeql_tempdir"] != ["contextmanager"] or any(
        decorators[name] for name in SOURCE_FUNCTIONS if name != "_codeql_tempdir"
    ):
        raise ValueError("Unexpected historical CodeQL decorators")
    # SHA-pinned shell's parser is selected, never a side-effectful import.
    code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    shell_scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "json": json, "os": os, "subprocess": subprocess, "signal": signal,
    }
    exec(code, shell_scope, shell_scope)
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Path": Path, "Any": Any, "os": os,
        "tempfile": tempfile, "shutil": shutil,
        "contextmanager": contextmanager, "run_cmd": run_cmd,
        "parse_json_maybe": shell_scope["parse_json_maybe"],
    }
    compiled = compile(
        ast.fix_missing_locations(ast.Module(
            body=[defs[name] for name in SOURCE_FUNCTIONS], type_ignores=[]
        )), str(SOURCE_PATH), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    )
    exec(compiled, scope, scope)
    return scope["scan_snapshot_with_codeql"]


class LocalCodeQLReplay:
    """Only a generated two-commit local Git repo and a fake CodeQL executable."""

    def __init__(self):
        self.temp = None
        self.calls = []
        self.clone_dir = None

    @staticmethod
    def _git(*args, cwd):
        result = subprocess.run(
            ["git", *args], cwd=cwd, check=True, capture_output=True,
            text=True, timeout=25,
        )
        return result.stdout.strip()

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="arno_codeql_local_")
        self.root = Path(self.temp.name).resolve()
        self.source = self.root / "source"
        self.source.mkdir()
        self._git("init", "--quiet", cwd=self.source)
        target = self.source / FILENAME
        target.parent.mkdir()
        target.write_text(BASE_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "safe base",
            cwd=self.source,
        )
        self.base_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        target.write_text(HEAD_CONTENT, encoding="utf-8")
        self._git("add", ".", cwd=self.source)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "synthetic introduced call",
            cwd=self.source,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.binary = self.bin / "codeql"
        compile(STUB, "<synthetic-codeql-stub>", "exec")
        self.binary.write_text(STUB, encoding="utf-8")
        self.binary.chmod(0o700)
        self.tmp_parent = self.root / "scanner-tmp"
        self.tmp_parent.mkdir()
        code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
        scope = {
            "__builtins__": __builtins__, "__name__": __name__,
            "json": json, "os": os, "subprocess": subprocess, "signal": signal,
        }
        exec(code, scope, scope)
        self.original_shell = scope["run_cmd"]
        self.original_codeql = _exact_original_codeql(self._restricted_command)
        return self

    def __exit__(self, *_exc):
        if self.temp:
            self.temp.cleanup()
            self.temp = None

    @staticmethod
    def files():
        return [{
            "filename": FILENAME, "category": "source", "status": "modified",
            "patch": PATCH, "additions": 4, "deletions": 0,
        }]

    def _restricted_command(self, cmd, cwd=None, timeout=None, env=None):
        if (not isinstance(cmd, list) or not cmd
            or any(not isinstance(s, str) for s in cmd)
            or env is not None):
            raise ValueError("Unapproved original CodeQL subprocess command")
        working = Path(cwd).resolve() if cwd is not None else None
        if cmd[:5] == ["git", "clone", "--depth", "1", REPO_URL] and len(cmd) == 6:
            if working is None or working.parent != self.tmp_parent:
                raise ValueError("Git clone outside synthetic CodeQL workspace")
            if working.name.startswith("miner-codeql-") is False or cmd[5] != "repo":
                raise ValueError("Unexpected CodeQL clone directory")
            self.clone_dir = working / "repo"
            allowed = cmd[:4] + ["file://" + str(self.source), cmd[5]]
        elif (
            len(cmd) == 6 and cmd[:5] == ["git", "fetch", "--depth", "1", "origin"]
            and cmd[5] in (self.base_sha, self.head_sha)
            and working == self.clone_dir
        ):
            allowed = cmd
        elif (
            len(cmd) == 3 and cmd[:2] == ["git", "checkout"]
            and cmd[2] in (self.base_sha, self.head_sha)
            and working == self.clone_dir
        ):
            allowed = cmd
        elif (
            len(cmd) == 9 and cmd[:3] == ["codeql", "database", "create"]
            and cmd[4:] == [
                "--language=python", "--source-root=" + str(self.clone_dir),
                "--ram=4096", "--threads=1", "--build-mode=none",
            ]
            and cwd is None and self.clone_dir is not None
        ):
            db = Path(cmd[3]).resolve()
            if db.parent != self.clone_dir.parent or db.name != "codeql-db":
                raise ValueError("Unexpected CodeQL db target")
            if (self.clone_dir / FILENAME).read_text() not in (
                BASE_CONTENT, HEAD_CONTENT,
            ):
                raise ValueError("CodeQL source content was not synthetic")
            if Path(shutil.which("codeql") or "").resolve() != self.binary:
                raise ValueError("Synthetic CodeQL was not selected")
            allowed = cmd
        elif (
            len(cmd) == 9 and cmd[:3] == ["codeql", "database", "analyze"]
            and cmd[4] == SUITE and cmd[5] == "--format=sarif-latest"
            and cmd[7:] == ["--ram=4096", "--threads=1"]
            and cwd is None and self.clone_dir is not None
        ):
            db = Path(cmd[3]).resolve()
            dest = Path(cmd[6].removeprefix("--output=")).resolve()
            if (db != self.clone_dir.parent / "codeql-db"
                or cmd[6] != "--output=" + str(dest)
                or dest != self.clone_dir.parent / "results.sarif"):
                raise ValueError("Unexpected SARIF/CodeQL analyze targets")
            if Path(shutil.which("codeql") or "").resolve() != self.binary:
                raise ValueError("Unexpected CodeQL executable")
            allowed = cmd
        else:
            raise ValueError("Unapproved CodeQL/Git command " + cmd[0])
        self.calls.append(cmd[0])
        return self.original_shell(allowed, cwd=cwd, timeout=timeout)

    def scan(self, repo_url, sha, *, language, build_mode, query_suite, timeout_seconds):
        if (
            self.temp is None or repo_url != REPO_URL
            or sha not in (self.base_sha, self.head_sha)
            or language != "python" or build_mode != "none" or query_suite != SUITE
            or timeout_seconds < 15 or timeout_seconds > 180
        ):
            raise ValueError("Only the fabricated CodeQL snapshot scan is permitted")
        with mock.patch.dict(os.environ, {
            "PATH": str(self.bin) + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
            "MINER_CODEQL_TMPDIR": str(self.tmp_parent),
            "CODEQL_RAM_MB": "4096", "CODEQL_THREADS": "1",
        }):
            if Path(shutil.which("codeql") or "").resolve() != self.binary:
                raise ValueError("Fake CodeQL binary missing from isolated PATH")
            return self.original_codeql(
                repo_url, sha, language=language, build_mode=build_mode,
                query_suite=query_suite, timeout_seconds=timeout_seconds,
            )
