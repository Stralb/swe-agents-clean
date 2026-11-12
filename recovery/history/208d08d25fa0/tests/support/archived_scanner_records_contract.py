"""SHA-pinned archived scanner evidence persistence, without scanner execution.

TEST ONLY: AST-extract exactly five definitions from the archived runner.
Never import scanner_runner.py: it imports subprocess-capable scanner modules.
All DB operations require the already-allocated disposable original Database.
"""
from __future__ import annotations

import __future__
import ast
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from src.db.database import Database
from tests.support.connected_original_dispatch import _require_disposable

SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/scanners/scanner_runner.py"
)
SOURCE_SHA256 = "f2507c1d487aebf8e9bd69cad8ff4c7315e781dbe8328cfaed423c2c3ace070f"
ALLOWLIST = (
    "_codeql_finding_type", "_insert_run", "_insert_finding",
    "_scanner_already_ran", "_clear_scanner",
)


def load_archived_scanner_records(db: Database) -> dict:
    """Bind exact archived SQLite evidence functions to one disposable DB."""
    _require_disposable(db)
    original = SOURCE_PATH.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Scanner-runner historical SHA-256 mismatch: {digest}")
    tree = ast.parse(original, filename=str(SOURCE_PATH))
    found = {
        x.name: x for x in tree.body
        if isinstance(x, ast.FunctionDef) and x.name in ALLOWLIST
    }
    if set(found) != set(ALLOWLIST):
        raise ValueError(f"Archived scanner functions missing: {set(ALLOWLIST)-set(found)}")
    if any(f.decorator_list for f in found.values()):
        raise ValueError("Scanner recording functions gained unreviewed decorators")
    code = compile(
        ast.fix_missing_locations(ast.Module(
            body=[found[name] for name in ALLOWLIST], type_ignores=[]
        )),
        str(SOURCE_PATH), "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    namespace = {
        "__name__": __name__,
        "__builtins__": __builtins__,
        "Database": Database, "Any": Any, "json": json,
        "log": logging.getLogger("arno.synthetic_scanner_evidence"),
    }
    exec(code, namespace, namespace)

    bound = {}
    for name in ALLOWLIST:
        original_fn = namespace[name]
        if name == "_codeql_finding_type":
            def checked_type(finding, _fn=original_fn):
                _require_disposable(db)
                return _fn(finding)
            bound[name] = checked_type
        else:
            def checked_db(*args, _fn=original_fn, **kwargs):
                _require_disposable(db)
                if not args or args[0] is not db:
                    raise TypeError("Archived scanner evidence must use its bound disposable DB")
                return _fn(*args, **kwargs)
            bound[name] = checked_db
    # Do not expose scanner_runner.scan_case or any scanner modules.
    return bound
