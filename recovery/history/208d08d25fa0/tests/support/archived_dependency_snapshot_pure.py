"""Run only exact SHA-pinned pure OSV/Trivy attribution AST functions.

TEST ONLY. The original modules include repo cloning and actual scanner
executables; they must never be imported. This file deliberately never selects
the scanning functions or injects run_cmd, subprocess, shutil or shell access.
All inputs are synthetic Python dictionaries.
"""
from __future__ import annotations

import __future__
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any

from src.scanners.dependency_diff import is_dependency_file

_ROOT = Path(__file__).resolve().parents[2]
OSV_PATH = _ROOT / "historical/miner/2026-10-20-live-export/src/scanners/osv_scanner.py"
TRIVY_PATH = _ROOT / "historical/miner/2026-10-20-live-export/src/scanners/trivy_scanner.py"
OSV_SHA256 = "4dda6859dbbf95af17bb43633cc2bdc8335bb12ec766d520cbbe5c9ea3f46834"
TRIVY_SHA256 = "e8e18cf902611d2c56f4bc993ea3d0465e34dbbee6af401c395fc44dd89d4620"

_OSV_ALLOWED = (
    "_advisory_ids", "_finding_key", "_normalise_dependency_path",
    "_dependency_paths_for_snapshot", "_rename_aliases",
    "_dependency_ancestor_directories", "_snapshot_finding_key",
    "_snapshot_status",
)
_TRIVY_ALLOWED = (
    "_dependency_paths", "_normalise_target", "_advisory_ids",
    "_finding_locator", "_snapshot_delta_findings",
    "_trivy_json_dict", "_trivy_normalise_path", "_trivy_paths_equal",
    "_trivy_finding_target", "_trivy_target_changed_by_pr",
    "_introduced_findings", "_combined_status",
)


def _load_pure_ast(path: Path, expected_hash: str, names: tuple[str, ...]) -> dict:
    source = path.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    if actual != expected_hash:
        raise ValueError(f"Historical scanner hash mismatch: {path.name}: {actual}")
    tree = ast.parse(source, filename=str(path))
    nodes = {node.name: node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in names}
    if set(nodes) != set(names) or any(nodes[name].decorator_list for name in names):
        raise ValueError("Historical pure function set changed; execution refused")
    selected = ast.Module(body=[nodes[name] for name in names], type_ignores=[])
    code = compile(
        ast.fix_missing_locations(selected), str(path), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    )
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Any": Any, "Path": Path,
        "PurePosixPath": __import__("pathlib").PurePosixPath,
        "json": json, "defaultdict": defaultdict,
        "is_dependency_file": is_dependency_file,
    }
    exec(code, scope, scope)
    # No scanner/runtime callables are returned, even from the untrusted AST.
    return {name: scope[name] for name in names}


def load_original_osv_attribution() -> dict:
    return _load_pure_ast(OSV_PATH, OSV_SHA256, _OSV_ALLOWED)


def load_original_trivy_attribution() -> dict:
    return _load_pure_ast(TRIVY_PATH, TRIVY_SHA256, _TRIVY_ALLOWED)
