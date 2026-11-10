"""Exact archived Gitleaks CLI wrapper with a disposable synthetic executable.

Tests exercise original subprocess.Popen, patch materialization and JSON parsing.
The executable is a short locally generated fixture, NEVER a real scanner and
NEVER any Wits, GitHub or user repository input.
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
from unittest import mock

BASE = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src"
)
GITLEAKS_PATH = BASE / "scanners/gitleaks_scanner.py"
GITLEAKS_SHA256 = "a63a4fb8910dbec9b26733da1d87ee416587733bc897b9b753c4cd30096c1807"
SHELL_PATH = BASE / "utils/shell.py"
SHELL_SHA256 = "f2daefdd7e39a0c1b4b45bafbf1821cb9968d4f3f7a83bb9bdb7adee3e5eb0e3"

SCANNER_FUNCTIONS = (
    "_is_baseline_file", "_is_placeholder_evidence", "_safe_path",
    "_added_lines_from_patch", "scan_files_with_gitleaks",
)
SCANNER_LITERALS = ("PLACEHOLDER_VALUES", "BASELINE_NAMES")
SHELL_FUNCTIONS = ("run_cmd", "parse_json_maybe")

_STUB_EXECUTABLE = r'''#!/usr/bin/env python3
"""This executable is NOT Gitleaks; it returns only predetermined synthetic data."""
import json
from pathlib import Path
import sys

args = sys.argv[1:]
if args == ["version"]:
    print("synthetic-gitleaks-stub 0.0.0")
    sys.exit(0)
required = ("detect", "--no-git", "--source", "--report-format",
            "json", "--report-path", "--redact")
if any(item not in args for item in required) or args[:2] != ["detect", "--no-git"]:
    print("Unexpected original CLI shape", file=sys.stderr)
    sys.exit(3)
root = Path(args[args.index("--source") + 1])
report = Path(args[args.index("--report-path") + 1])
if not root.is_dir() or report != root / "gitleaks.json":
    print("Invalid synthetic directory", file=sys.stderr)
    sys.exit(4)
target = root / "fixture" / "app.ts"
data = target.read_text(encoding="utf-8") if target.exists() else ""
if "SYNTHETIC_FAIL_NO_REPORT" in data:
    print("Synthetic CLI failure without report", file=sys.stderr)
    sys.exit(2)
findings = []
if "SYNTHETIC_KEY_SIGNAL" in data:
    findings.append({
        "File": str(target),
        "StartLine": 1,
        "RuleID": "synthetic-rule",
        "Description": "Synthetic fixture signal; NOT a detected secret",
        "Match": "<redacted>",
    })
report.write_text(json.dumps(findings), encoding="utf-8")
print("synthetic-stub completed")
sys.exit(1 if findings else 0)
'''


def _exact_defs(path: Path, sha256: str, names, *, literals=()):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != sha256:
        raise ValueError(f"Historical source hash mismatch: {path.name} {digest}")
    tree = ast.parse(data, filename=str(path))
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names}
    if set(defs) != set(names) or any(n.decorator_list for n in defs.values()):
        raise ValueError("Unapproved change to historical scanner AST")
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else None
            if name in literals:
                values[name] = ast.literal_eval(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id in literals:
                values[node.target.id] = ast.literal_eval(node.value)
    if set(values) != set(literals):
        raise ValueError("Missing historical scanner constants")
    return compile(
        ast.fix_missing_locations(
            ast.Module(body=[defs[name] for name in names], type_ignores=[])
        ),
        str(path), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    ), values


def load_original_gitleaks_process():
    """Return the SHA-pinned original Gitleaks function, with original shell."""
    shell_code, _ = _exact_defs(SHELL_PATH, SHELL_SHA256, SHELL_FUNCTIONS)
    shell_scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "json": json, "os": os, "signal": signal, "subprocess": subprocess,
    }
    exec(shell_code, shell_scope, shell_scope)
    scanner_code, constants = _exact_defs(
        GITLEAKS_PATH, GITLEAKS_SHA256, SCANNER_FUNCTIONS,
        literals=SCANNER_LITERALS,
    )
    scanner_scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Path": Path, "PurePosixPath": PurePosixPath,
        "shutil": shutil, "tempfile": tempfile,
        "run_cmd": shell_scope["run_cmd"],
        "parse_json_maybe": shell_scope["parse_json_maybe"],
        **constants,
    }
    exec(scanner_code, scanner_scope, scanner_scope)
    return scanner_scope["scan_files_with_gitleaks"]


class DisposableGitleaksProcess:
    """Prevent any non-fixture executable or non-synthetic file being scanned."""

    def __init__(self):
        self._scan = load_original_gitleaks_process()

    @staticmethod
    def _check_files(files):
        if not isinstance(files, list):
            raise TypeError("A list of synthetic patch rows is required")
        for item in files:
            if not isinstance(item, dict):
                raise TypeError("Each row must be a synthetic dictionary")
            filename = item.get("filename")
            patch = item.get("patch")
            if not isinstance(filename, str) or not isinstance(patch, str):
                raise ValueError("Synthetic file and patch must both be explicit strings")
            parsed = PurePosixPath(filename)
            if (
                not filename.startswith("fixture/")
                or filename.startswith("/")
                or "\\" in filename
                or ".." in filename.split("/")
                or not parsed.name
                or (patch and "SYNTHETIC" not in patch)
            ):
                raise ValueError("Only fixture/ paths with synthetic patch text are allowed")

    def run(self, files):
        self._check_files(files)
        with tempfile.TemporaryDirectory(prefix="arno_stub_gitleaks_") as td:
            binary = Path(td) / "gitleaks"
            binary.write_text(_STUB_EXECUTABLE, encoding="utf-8")
            binary.chmod(0o700)
            with mock.patch.dict(os.environ, {
                "PATH": td + os.pathsep + os.environ.get("PATH", ""),
            }):
                if Path(shutil.which("gitleaks") or "").resolve() != binary.resolve():
                    raise RuntimeError("Synthetic fixture binary did not win PATH")
                return self._scan(files)
