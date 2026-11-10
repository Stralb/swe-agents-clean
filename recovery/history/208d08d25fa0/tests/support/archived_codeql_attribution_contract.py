"""Test-only replay of the original CodeQL diff attribution functions.

Original bytes are SHA-256 verified. We extract only 11 pure AST functions and
two literal lookup dictionaries. Never import CodeQL's subprocess, tempdir,
clone, query executor, or any external scanner binary.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
from pathlib import Path
from typing import Any, Iterable

SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/scanners/codeql_scanner.py"
)
SOURCE_SHA256 = "03bad76387b998d3b8978299cc9322a3a7a792c6e46fa4ce7338c4808fd6f198"
NAMES = (
    "_norm_path", "codeql_languages_for_files", "has_codeql_source_changes",
    "has_python_source_changes", "default_query_suite_for_language",
    "added_line_numbers_by_file", "_sarif_location_tuple",
    "_extract_all_locations", "finding_touches_added_lines",
    "filter_findings_to_pr_delta", "diff_findings",
)
CONSTANTS = ("CODEQL_LANGUAGE_EXTENSIONS", "DEFAULT_QUERY_SUITES")


def load_original_codeql_attribution() -> dict:
    """Return only exact historical pure CodeQL methods, never tool execution."""
    data = SOURCE_PATH.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Historical CodeQL source hash mismatch: {digest}")
    tree = ast.parse(data, filename=str(SOURCE_PATH))
    defs = {
        n.name: n for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in NAMES
    }
    if set(defs) != set(NAMES):
        raise ValueError(f"Missing original CodeQL functions: {set(NAMES) - set(defs)}")
    if any(n.decorator_list for n in defs.values()):
        raise ValueError("Unreviewed original CodeQL decorators are forbidden")
    literals = {}
    for n in tree.body:
        name = None
        if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            name = n.target.id
        elif isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            name = n.targets[0].id
        if name in CONSTANTS:
            literals[name] = ast.literal_eval(n.value)
    if set(literals) != set(CONSTANTS):
        raise ValueError("Original CodeQL language/query literals missing")
    code = compile(
        ast.fix_missing_locations(ast.Module(
            body=[defs[n] for n in NAMES], type_ignores=[]
        )), str(SOURCE_PATH), "exec",
        flags=__future__.annotations.compiler_flag, dont_inherit=True,
    )
    scope = {
        "__builtins__": __builtins__, "__name__": __name__,
        "Any": Any, "Iterable": Iterable, **literals,
    }
    exec(code, scope, scope)
    return {key: scope[key] for key in NAMES}
