"""Strict offline replay of the archived miner's SQLite worker queue methods.

Never imports the historical job_queue module, which imports the live scanner
runner. Only verified AST definitions for job lifecycle operations are executed
using the disposable original Database. scan_case/run_scanner_job, Slurm, process
management and real scanner binaries are not available in the namespace.
"""
from __future__ import annotations

import __future__
import ast
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import logging
from pathlib import Path
import uuid

from src.db.database import Database
from src.filters.tool_applicability import route_reasons
from src.pipeline.case_builder import update_case_tags_and_status
from src.pipeline.case_status import sync_case_statuses
from tests.support.connected_original_dispatch import _require_disposable

SOURCE_PATH = Path(__file__).resolve().parents[2] / (
    "historical/miner/2026-10-20-live-export/src/workers/job_queue.py"
)
SOURCE_SHA256 = "07a8fa5844c137816078348dbff856fdf0a41b0e53a67013a5deb441e265a73d"
CONSTANTS = ("JOB_PRIORITY", "JOB_SCANNERS", "REQUIRED_JOB_TYPES")
FUNCTIONS = (
    "_case_select", "files_for_case", "applicable_job_types", "case_priority",
    "seed_scanner_jobs", "claim_job", "finish_job", "heartbeat",
    "update_case_stages", "reset_running_jobs_on_start",
    "_scanner_config_for_job", "_job_status_from_runs",
    "_job_status_from_scanner_runs", "sync_jobs_from_scanner_runs",
)


def load_original_queue(db: Database) -> dict:
    """Load only approved historical functions and constants with path guards."""
    _require_disposable(db)
    raw = SOURCE_PATH.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"Historical job queue hash mismatch: {digest}")
    tree = ast.parse(raw, filename=str(SOURCE_PATH))

    extracted: dict[str, ast.FunctionDef] = {
        node.name: node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS
    }
    if set(extracted) != set(FUNCTIONS):
        raise ValueError(f"Missing historical queue functions: {set(FUNCTIONS)-set(extracted)}")
    if any(f.decorator_list for f in extracted.values()):
        raise ValueError("Unexpected decorated historical worker functions")

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ClaimedJob"]
    if len(classes) != 1:
        raise ValueError("Expected exactly one historical ClaimedJob class")
    decorator = classes[0].decorator_list
    if (len(decorator) != 1 or not isinstance(decorator[0], ast.Call)
            or not isinstance(decorator[0].func, ast.Name)
            or decorator[0].func.id != "dataclass"
            or len(decorator[0].args) != 0
            or len(decorator[0].keywords) != 1
            or decorator[0].keywords[0].arg != "frozen"
            or not isinstance(decorator[0].keywords[0].value, ast.Constant)
            or decorator[0].keywords[0].value.value is not True):
        raise ValueError("Historical ClaimedJob decorator unexpectedly changed")

    constants = {}
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            value = node.target.id
        if value in CONSTANTS:
            constants[value] = ast.literal_eval(node.value)
    if set(constants) != set(CONSTANTS):
        raise ValueError("Expected original worker priority and job-type literals")

    code = compile(
        ast.fix_missing_locations(ast.Module(
            body=[classes[0], *(extracted[n] for n in FUNCTIONS)], type_ignores=[]
        )),
        str(SOURCE_PATH), "exec",
        flags=__future__.annotations.compiler_flag,
        dont_inherit=True,
    )
    scope = {
        "__builtins__": __builtins__,
        "__name__": __name__,  # dataclass annotations require a registered module
        "Database": Database,
        "dataclass": dataclass,
        "uuid": uuid,
        "copy": copy,
        "datetime": datetime, "timedelta": timedelta, "timezone": timezone,
        "route_reasons": route_reasons,
        "update_case_tags_and_status": update_case_tags_and_status,
        "sync_case_statuses": sync_case_statuses,
        "log": logging.getLogger("arno.archived_queue_fixture"),
        **constants,
    }
    exec(code, scope, scope)

    bound: dict = {}
    for name in FUNCTIONS:
        func = scope[name]
        def checked(*args, _func=func, _name=name, **kwargs):
            _require_disposable(db)
            if not args or args[0] is not db:
                raise TypeError("Worker replay only accepts its bound disposable database")
            if _name == "_scanner_config_for_job":
                return _func(*args[1:], **kwargs)  # pure helper has no DB argument
            return _func(*args, **kwargs)
        bound[name] = checked
    bound["ClaimedJob"] = scope["ClaimedJob"]
    bound["JOB_PRIORITY"] = constants["JOB_PRIORITY"]
    bound["JOB_SCANNERS"] = constants["JOB_SCANNERS"]
    bound["REQUIRED_JOB_TYPES"] = constants["REQUIRED_JOB_TYPES"]
    return bound
