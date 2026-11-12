"""SHA-pinned archived Semgrep wrapper, restricted to a local synthetic Git repo.

This test-only adapter rewrites ONLY the original git-clone command from an
example.invalid URL to a self-generated local Git repository. All remaining git
and scanner commands go through the SHA-pinned original run_cmd. Never use on
user repositories, remote GitHub URLs, production databases or Wits paths.
"""
from __future__ import annotations

import __future__
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
from unittest import mock

from tests.support.archived_codeql_attribution_contract import (
    load_original_codeql_attribution,
)
from tests.support.archived_gitleaks_process import (
    _exact_defs, SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS,
)

SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/scanners/semgrep_scanner.py"
)
SOURCE_SHA256 = "cd5e3774840c22f3968601f005fa8e65d808b597d6d8580cc045ef0fc2feec0a"
METHODS = (
    "changed_semgrep_paths", "_severity", "_cwe", "_metadata_list",
    "is_test_or_example_path", "is_low_confidence_audit",
    "parse_semgrep_json", "semgrep_rejection_reasons",
    "classify_semgrep_to_pr_delta", "scan_head_with_semgrep",
)
LITERALS = ("TEST_OR_EXAMPLE_PREFIXES", "SEMGREP_SOURCE_EXTENSIONS")
REPO_URL = "https://example.invalid/fixture/local-semgrep"
SCRIPT = 'synthetic_smoke("ARNO_SYNTHETIC_MARKER")\n'
SOURCE_NAMES = ("src/app.py", "tests/test_fixture.py")
ADDED_PATCH = '@@ -0,0 +1 @@\n+' + SCRIPT
RULE = """rules:
  - id: arno-synthetic-smoke
    languages: [python]
    message: Harmless synthetic marker for reproducibility checks
    severity: WARNING
    pattern: synthetic_smoke(...)
    metadata:
      category: correctness
      confidence: HIGH
      likelihood: HIGH
"""
STUB = r'''#!/usr/bin/env python3
"""Deterministic Semgrep-shaped local stub: does not analyze code."""
import json
from pathlib import Path
import sys

args = sys.argv[1:]
expected = ("--config", "--json", "--metrics=off", "--quiet", "--output")
if any(x not in args for x in expected):
    sys.exit(4)
targets = args[args.index("--output") + 2:]
if targets != ["src/app.py", "tests/test_fixture.py"]:
    print("unexpected scanner targets", file=sys.stderr)
    sys.exit(5)
results = []
for target in targets:
    path = Path(target)
    if path.read_text(encoding="utf-8") != 'synthetic_smoke("ARNO_SYNTHETIC_MARKER")\n':
        sys.exit(6)
    results.append({
        "check_id": "arno-synthetic-smoke",
        "path": target,
        "start": {"line": 1, "col": 1},
        "extra": {
            "message": "Synthetic check only",
            "severity": "WARNING",
            "metadata": {
                "category": "correctness",
                "confidence": "HIGH",
                "likelihood": "HIGH"
            }
        }
    })
output = Path(args[args.index("--output") + 1])
output.write_text(json.dumps({"results": results, "errors": []}), encoding="utf-8")
'''


def load_original_semgrep_scan(restricted_run_cmd):
    """Compile original Semgrep functions, never its side-effectful module."""
    semgrep_code, constants = _exact_defs(
        SOURCE_PATH, SOURCE_SHA256, METHODS, literals=LITERALS,
    )
    shell_code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    shell_scope = {"__builtins__": __builtins__, "__name__": __name__,
                   "json": json, "os": os, "signal": __import__("signal"),
                   "subprocess": subprocess}
    exec(shell_code, shell_scope, shell_scope)
    codeql = load_original_codeql_attribution()
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Any": Any, "Path": Path, "json": json, "shutil": shutil,
        "tempfile": tempfile, "run_cmd": restricted_run_cmd,
        "parse_json_maybe": shell_scope["parse_json_maybe"],
        "_norm_path": codeql["_norm_path"],
        "added_line_numbers_by_file": codeql["added_line_numbers_by_file"],
        "finding_touches_added_lines": codeql["finding_touches_added_lines"],
        **constants,
    }
    exec(semgrep_code, scope, scope)
    return scope["scan_head_with_semgrep"]


class LocalSemgrepReplay:
    """One synthetic local git commit and one fixed local Semgrep rule."""

    def __init__(self, *, semgrep_executable=None):
        self._temporary = None
        self._requested_executable = semgrep_executable
        self.calls = []
        self.clone_dir = None

    @staticmethod
    def _git(*args, cwd=None):
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True,
            text=True, timeout=30, check=True,
        )
        return result.stdout.strip()

    def __enter__(self):
        self._temporary = tempfile.TemporaryDirectory(prefix="arno_semgrep_local_")
        self.root = Path(self._temporary.name).resolve()
        self.source_dir = self.root / "source"
        self.source_dir.mkdir()
        for filename in SOURCE_NAMES:
            path = self.source_dir / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(SCRIPT, encoding="utf-8")
        self._git("init", "--quiet", cwd=self.source_dir)
        self._git("add", ".", cwd=self.source_dir)
        self._git(
            "-c", "user.name=Synthetic Fixture",
            "-c", "user.email=fixture@example.invalid",
            "commit", "--quiet", "-m", "Initial synthetic fixture",
            cwd=self.source_dir,
        )
        self.head_sha = self._git("rev-parse", "HEAD", cwd=self.source_dir)
        self.rule_file = self.root / "synthetic-rules.yaml"
        self.rule_file.write_text(RULE, encoding="utf-8")
        if self._requested_executable is None:
            stub_dir = self.root / "bin"
            stub_dir.mkdir()
            binary = stub_dir / "semgrep"
            binary.write_text(STUB, encoding="utf-8")
            binary.chmod(0o700)
            self.binary = binary
        else:
            self.binary = Path(self._requested_executable).resolve()
            if self.binary.name != "semgrep" or not self.binary.is_file():
                raise ValueError("Only the verified semgrep CLI path is accepted")
        self._shell_code, _ = _exact_defs(
            SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS,
        )
        scope = {"__builtins__": __builtins__, "__name__": __name__,
                 "json": json, "os": os, "signal": __import__("signal"),
                 "subprocess": subprocess}
        exec(self._shell_code, scope, scope)
        self._shell_run = scope["run_cmd"]
        self._scanner = load_original_semgrep_scan(self._restricted_cmd)
        return self

    def __exit__(self, kind, value, traceback):
        if self._temporary is not None:
            self._temporary.cleanup()
            self._temporary = None

    @staticmethod
    def synthetic_files():
        return [
            {"filename": p, "status": "added", "patch": ADDED_PATCH,
             "additions": 1, "deletions": 0}
            for p in SOURCE_NAMES
        ]

    def _restricted_cmd(self, cmd, cwd=None, timeout=None, env=None):
        if env is not None or not isinstance(cmd, list) or not cmd:
            raise ValueError("Unexpected command execution context")
        cwd_path = Path(cwd).resolve() if cwd is not None else None
        if cmd == ["git", "clone", "--depth", "1", REPO_URL, "repo"]:
            if (
                cwd_path is None or not cwd_path.is_dir()
                or not str(cwd_path).startswith(str(Path(tempfile.gettempdir()).resolve()) + os.sep)
                or cwd_path == self.root
            ):
                raise ValueError("Expected archived scanner disposable checkout")
            self.clone_dir = cwd_path / "repo"
            command = [
                "git", "clone", "--depth", "1",
                "file://" + str(self.source_dir), "repo",
            ]
        elif cmd == ["git", "fetch", "--depth", "1", "origin", self.head_sha]:
            if cwd_path != self.clone_dir:
                raise ValueError("Unexpected archived Git fetch location")
            command = cmd
        elif cmd == ["git", "checkout", self.head_sha]:
            if cwd_path != self.clone_dir:
                raise ValueError("Unexpected archived Git checkout location")
            command = cmd
        elif cmd[0] == "semgrep":
            expected = [
                "semgrep", "--config", str(self.rule_file), "--json",
                "--metrics=off", "--quiet", "--output",
            ]
            if (
                cwd_path != self.clone_dir or cmd[:7] != expected
                or len(cmd) != 10 or cmd[8:] != list(SOURCE_NAMES)
                or Path(cmd[7]).resolve() != self.clone_dir.parent / "semgrep.json"
            ):
                raise ValueError("Unexpected Semgrep executable or target arguments")
            if Path(shutil.which("semgrep") or "").resolve() != self.binary:
                raise ValueError("Unverified scanner executable on PATH")
            command = cmd
        else:
            raise ValueError(f"Unapproved archived subprocess command: {cmd[0]!r}")
        self.calls.append((cmd[0], tuple(cmd[1:])))
        return self._shell_run(command, cwd=cwd, timeout=timeout)

    def scan(self, repo_url, head_sha, files, *, timeout_seconds=120):
        if repo_url != REPO_URL or head_sha != self.head_sha:
            raise ValueError("Only the new synthetic git repository is allowed")
        if files != self.synthetic_files():
            raise ValueError("Only exact original synthetic PR patches are allowed")
        if self._temporary is None:
            raise ValueError("LocalSemgrepReplay context is closed")
        executable_dir = str(self.binary.parent)
        with mock.patch.dict(os.environ, {
            "PATH": executable_dir + os.pathsep + "/usr/bin:/bin",
            "SEMGREP_SEND_METRICS": "off",
            "SEMGREP_ENABLE_VERSION_CHECK": "0",
            "SEMGREP_DISABLE_VERSION_CHECK": "1",
            "SEMGREP_SETTINGS_FILE": str(self.root / "settings.yml"),
        }):
            if Path(shutil.which("semgrep") or "").resolve() != self.binary:
                raise ValueError("Executable path was not successfully isolated")
            return self._scanner(
                repo_url, head_sha, files,
                semgrep_config=str(self.rule_file),
                timeout_seconds=timeout_seconds,
            )
