"""Replay the exact archived worker dispatcher against synthetic-only scanners.

Test-only: SHA-pin AST for _case_select, _scanner_config_for_job and
run_scanner_job. The historical job_queue module is never imported. No
live worker, scanner executable, network client or cluster process is available.
"""
from __future__ import annotations

import __future__
import ast
import copy
from dataclasses import dataclass, fields, is_dataclass
import hashlib
import logging

from src.db.database import Database
from tests.support.archived_fixture_scan_case import (
    ArchivedFixtureScanCase, FixtureScannerProviders,
)
from tests.support.archived_job_queue_contract import (
    SOURCE_PATH, SOURCE_SHA256, load_original_queue,
)
from tests.support.connected_original_dispatch import _require_disposable

_FUNCTIONS = ("_case_select", "_scanner_config_for_job", "run_scanner_job")
_SCANNERS = frozenset(
    ("gitleaks", "dependency_downgrade", "osv", "trivy", "semgrep", "codeql")
)


@dataclass(frozen=True)
class FixtureWorkerSettings:
    """An explicit dict of fixture options; never the historical Settings type."""

    config: dict


class ArchivedFixtureWorker:
    """Claim/execute/finish through exact original methods on a temporary DB."""

    def __init__(self, db: Database, backends: FixtureScannerProviders):
        _require_disposable(db)
        if not isinstance(backends, FixtureScannerProviders):
            raise TypeError("Explicit synthetic FixtureScannerProviders required")
        raw = SOURCE_PATH.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != SOURCE_SHA256:
            raise ValueError(f"Historical worker source hash mismatch: {digest}")

        tree = ast.parse(raw, filename=str(SOURCE_PATH))
        definitions = {
            node.name: node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in _FUNCTIONS
        }
        if set(definitions) != set(_FUNCTIONS):
            raise ValueError(f"Original worker methods missing: {set(_FUNCTIONS)-set(definitions)}")
        if any(node.decorator_list for node in definitions.values()):
            raise ValueError("Unexpected decorator on historical worker method")

        self.db = db
        self.queue = load_original_queue(db)
        self.scanner = ArchivedFixtureScanCase(db, backends)
        source = compile(
            ast.fix_missing_locations(ast.Module(
                body=[definitions[name] for name in _FUNCTIONS], type_ignores=[]
            )),
            str(SOURCE_PATH), "exec",
            flags=__future__.annotations.compiler_flag, dont_inherit=True,
        )

        def fixture_scan_case(actual_db, case, config):
            if actual_db is not db:
                raise TypeError("Archived worker must use its bound disposable database")
            return self.scanner.run(case, config)

        scope = {
            "__builtins__": __builtins__, "__name__": __name__,
            "copy": copy,
            "log": logging.getLogger("arno.synthetic_archived_worker"),
            "scan_case": fixture_scan_case,
            "finish_job": self.queue["finish_job"],
            "_job_status_from_scanner_runs": self.queue["_job_status_from_scanner_runs"],
            "update_case_stages": self.queue["update_case_stages"],
        }
        exec(source, scope, scope)
        self._original_run_scanner_job = scope["run_scanner_job"]

    def run(self, job, settings: FixtureWorkerSettings) -> None:
        """Run a previously claimed fixture job. Refuse any non-fixture input."""
        _require_disposable(self.db)
        if not isinstance(settings, FixtureWorkerSettings):
            raise TypeError("Only FixtureWorkerSettings is accepted")
        config = settings.config
        if not isinstance(config, dict) or set(config) - {"scanners", "cache"}:
            raise ValueError("Only explicit fixture scanner/cache configuration is allowed")
        scanners = config.get("scanners")
        if not isinstance(scanners, dict) or not _SCANNERS.issubset(scanners):
            raise ValueError("All six scanner flags are required")
        if any(type(scanners[name]) is not bool for name in _SCANNERS):
            raise ValueError("All six scanner flags must be literal booleans")
        if not isinstance(config.get("cache", {}), dict):
            raise ValueError("Fixture cache must be a dictionary")
        # Both queue loaders SHA-compile the same archived dataclass separately,
        # yielding distinct Python class identities. Validate the exact frozen
        # dataclass contract and then attest all fields against the claimed DB row.
        expected_type = self.queue["ClaimedJob"]
        if not (
            is_dataclass(job)
            and type(job).__name__ == expected_type.__name__
            and type(job).__module__ == expected_type.__module__
            and tuple(field.name for field in fields(job))
                == tuple(field.name for field in fields(expected_type))
            and all(type(getattr(job, name)) is int
                    for name in ("id", "case_id", "priority", "attempts"))
            and type(job.job_type) is str
        ):
            raise TypeError("Only an original-shape archived ClaimedJob is accepted")
        if job.job_type not in self.queue["JOB_SCANNERS"]:
            raise ValueError("Unknown scanner job type")
        row = self.db.one(
            "SELECT case_id,job_type,status,attempts FROM scanner_jobs WHERE id=?",
            (job.id,),
        )
        if (
            not row or row["status"] != "running"
            or int(row["case_id"]) != job.case_id
            or row["job_type"] != job.job_type
            or int(row["attempts"]) != job.attempts
        ):
            raise ValueError("Job was not claimed in the bound disposable database")
        repo = self.db.one(
            """SELECT r.html_url AS url FROM cases c
            JOIN repos r ON r.id=c.repo_id WHERE c.id=?""",
            (job.case_id,),
        )
        if not repo or not isinstance(repo["url"], str) or not repo["url"].startswith(
            "https://example.invalid/"
        ):
            raise ValueError("Worker may only scan a synthetic example.invalid case")
        self._original_run_scanner_job(self.db, settings, job)
