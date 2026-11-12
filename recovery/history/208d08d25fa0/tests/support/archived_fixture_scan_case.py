"""Execute exact archived scan_case with exclusively synthetic scanner backends.

TEST-ONLY. The historical scan runner is SHA-pinned; its module, imports and
external scanners are never loaded. Every callable scanner provider must be
injected with in-memory fixtures. All six original scanner branches are covered.
"""
from __future__ import annotations

import __future__
import ast
from copy import deepcopy
from pathlib import Path

from src.db.database import Database
from tests.support.archived_scanner_records_contract import (
    SOURCE_PATH, SOURCE_SHA256, load_archived_scanner_records,
)
from tests.support.archived_codeql_attribution_contract import load_original_codeql_attribution
from tests.support.connected_original_dispatch import _require_disposable


class MissingScannerFixture(BaseException):
    """An incomplete offline scan must not be masked as scanner negative."""


class FixtureScannerProviders:
    """Synthetic outputs only. No system/network/program access."""

    def __init__(
        self, *, gitleaks=(), codeql=None, dependency_diff=(),
        osv=(), trivy=(), semgrep=(),
    ):
        self.gitleaks_responses = list(gitleaks)
        self.codeql_responses = dict(codeql or {})
        self.dependency_responses = list(dependency_diff)
        self.osv_responses = list(osv)
        self.trivy_responses = list(trivy)
        self.semgrep_responses = list(semgrep)
        self.calls: list[tuple] = []

    @staticmethod
    def _require_synthetic_url(repo_url):
        if not isinstance(repo_url, str) or not repo_url.startswith("https://example.invalid/"):
            raise MissingScannerFixture("Only example.invalid synthetic repository is allowed")

    @staticmethod
    def _take_response(responses, scanner, width):
        if not responses:
            raise MissingScannerFixture(f"Missing synthetic {scanner} response")
        response = deepcopy(responses.pop(0))
        if (
            not isinstance(response, (tuple, list))
            or len(response) != width
            or not isinstance(response[0], list)
            or any(not isinstance(finding, dict) for finding in response[0])
            or any(not isinstance(meta, dict) for meta in response[1:])
        ):
            raise MissingScannerFixture(f"Malformed synthetic {scanner} response")
        return tuple(response)

    def scan_files_with_gitleaks(self, files):
        self.calls.append(("gitleaks", len(files)))
        if not self.gitleaks_responses:
            raise MissingScannerFixture("Missing synthetic Gitleaks response")
        return deepcopy(self.gitleaks_responses.pop(0))

    def scan_snapshot_with_codeql(
        self, repo_url, sha, *, language, build_mode, query_suite, timeout_seconds
    ):
        self.calls.append(("codeql", sha, language, query_suite))
        self._require_synthetic_url(repo_url)
        if sha not in self.codeql_responses:
            raise MissingScannerFixture(f"Missing synthetic CodeQL snapshot: {sha!r}")
        return deepcopy(self.codeql_responses[sha])

    def detect_dependency_regressions(self, files):
        if not self.dependency_responses:
            raise MissingScannerFixture("Missing synthetic dependency-diff response")
        findings = deepcopy(self.dependency_responses.pop(0))
        if not isinstance(findings, list) or any(not isinstance(x, dict) for x in findings):
            raise MissingScannerFixture("Malformed synthetic dependency-diff response")
        self.calls.append(("dependency-diff", len(files)))
        return findings

    def scan_dependency_snapshots(
        self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
    ):
        self._require_synthetic_url(repo_url)
        response = self._take_response(self.osv_responses, "OSV", 4)
        self.calls.append(("osv", base_sha, head_sha, timeout_seconds, len(files)))
        return response

    def scan_dependency_snapshots_with_trivy(
        self, repo_url, base_sha, head_sha, files, *, timeout_seconds,
    ):
        self._require_synthetic_url(repo_url)
        response = self._take_response(self.trivy_responses, "Trivy", 4)
        self.calls.append(("trivy", base_sha, head_sha, timeout_seconds, len(files)))
        return response

    def scan_head_with_semgrep(
        self, repo_url, head_sha, files, *, semgrep_config, timeout_seconds,
    ):
        self._require_synthetic_url(repo_url)
        response = self._take_response(self.semgrep_responses, "Semgrep", 2)
        self.calls.append(
            ("semgrep", head_sha, semgrep_config, timeout_seconds, len(files))
        )
        return response


class ArchivedFixtureScanCase:
    """Run the unchanged archived scan_case over one prevalidated disposable DB."""

    _APPROVED = ("gitleaks", "dependency_downgrade", "osv", "trivy", "semgrep", "codeql")

    def __init__(self, db: Database, backends: FixtureScannerProviders):
        _require_disposable(db)
        if not isinstance(backends, FixtureScannerProviders):
            raise TypeError("Explicit FixtureScannerProviders required")
        self.db = db
        self.backends = backends
        records = load_archived_scanner_records(db)
        codeql = load_original_codeql_attribution()
        raw = SOURCE_PATH.read_bytes()
        import hashlib
        digest = hashlib.sha256(raw).hexdigest()
        if digest != SOURCE_SHA256:
            raise ValueError(f"Unapproved scanner runner SHA: {digest}")
        tree = ast.parse(raw, filename=str(SOURCE_PATH))
        selected = [f for f in tree.body if isinstance(f, ast.FunctionDef) and f.name == "scan_case"]
        if len(selected) != 1 or selected[0].decorator_list:
            raise ValueError("Missing or decorated historical scan_case")
        executable = compile(
            ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
            str(SOURCE_PATH), "exec",
            flags=__future__.annotations.compiler_flag, dont_inherit=True,
        )
        scope = {
            "__builtins__": __builtins__, "__name__": __name__,
            "_insert_run": records["_insert_run"],
            "_insert_finding": records["_insert_finding"],
            "_scanner_already_ran": records["_scanner_already_ran"],
            "_clear_scanner": records["_clear_scanner"],
            "_codeql_finding_type": records["_codeql_finding_type"],
            "scan_files_with_gitleaks": backends.scan_files_with_gitleaks,
            "detect_dependency_regressions": backends.detect_dependency_regressions,
            "scan_dependency_snapshots": backends.scan_dependency_snapshots,
            "scan_dependency_snapshots_with_trivy": backends.scan_dependency_snapshots_with_trivy,
            "scan_head_with_semgrep": backends.scan_head_with_semgrep,
            "scan_snapshot_with_codeql": backends.scan_snapshot_with_codeql,
            "codeql_languages_for_files": codeql["codeql_languages_for_files"],
            "default_query_suite_for_language": codeql["default_query_suite_for_language"],
            "diff_findings": codeql["diff_findings"],
            "filter_findings_to_pr_delta": codeql["filter_findings_to_pr_delta"],
        }
        exec(executable, scope, scope)
        self._original_scan_case = scope["scan_case"]

    def run(self, case: dict, config: dict):
        _require_disposable(self.db)
        if not isinstance(case, dict) or not isinstance(config, dict):
            raise TypeError("Synthetic case and config dictionaries required")
        sc = config.get("scanners")
        if not isinstance(sc, dict):
            raise ValueError("All scanner flags must be explicitly specified")
        if set(sc).intersection(self._APPROVED) != set(self._APPROVED):
            raise ValueError("Missing one or more explicit scanner flags")
        for key in self._APPROVED:
            if not isinstance(sc[key], bool):
                raise ValueError(f"Scanner flag {key} must be a literal bool")
        if "repo_url" in case and case["repo_url"] is not None:
            if not isinstance(case["repo_url"], str) or not case["repo_url"].startswith("https://example.invalid/"):
                raise ValueError("Only synthetic example.invalid repository URLs are allowed")
        case_id = int(case.get("case_id") or 0)
        pr_id = int(case.get("pr_id") or 0)
        row = self.db.one("SELECT pr_id FROM cases WHERE id=?", (case_id,))
        if not row or int(row["pr_id"]) != pr_id:
            raise ValueError("The supplied case/PR must exist in the disposable database")
        return self._original_scan_case(self.db, case, config)
