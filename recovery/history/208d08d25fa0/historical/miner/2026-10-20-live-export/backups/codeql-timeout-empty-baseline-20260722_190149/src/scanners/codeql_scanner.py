from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from src.utils.shell import parse_json_maybe, run_cmd


def _norm_path(path: str | None) -> str:
    p = (path or "").replace("\\", "/").lstrip("./")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p


CODEQL_LANGUAGE_EXTENSIONS: dict[str, tuple[str, ...]] = {
    "python": (".py", ".pyi"),
    "javascript-typescript": (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"),
    "ruby": (".rb",),
    "go": (".go",),
    "csharp": (".cs",),
    "java-kotlin": (".java", ".kt", ".kts"),
    "c-cpp": (".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".hxx"),
}



def _codeql_tmp_parent() -> Path:
    """Return a Linux-local temp parent for CodeQL workspaces.

    CodeQL database creation can leave files briefly open while Python exits the
    temporary context, especially under WSL/Windows-mounted paths. Keep CodeQL
    temp work under a Linux filesystem by default and make the location
    overrideable for clusters.
    """
    raw = (
        os.environ.get("MINER_CODEQL_TMPDIR")
        or os.environ.get("CODEQL_TMPDIR")
        or os.environ.get("MINER_TMPDIR")
        or os.environ.get("TMPDIR")
        or "/tmp/miner-codeql-tmp"
    )
    parent = Path(raw).expanduser()
    parent.mkdir(parents=True, exist_ok=True)
    return parent


@contextmanager
def _codeql_tempdir():
    """TemporaryDirectory wrapper that never lets cleanup failure mark scans failed."""
    parent = _codeql_tmp_parent()
    td_obj = tempfile.TemporaryDirectory(
        prefix="miner-codeql-",
        dir=str(parent),
        ignore_cleanup_errors=True,
    )
    try:
        yield Path(td_obj.name)
    finally:
        try:
            td_obj.cleanup()
        except Exception:
            # Cleanup errors are operational noise in WSL/CodeQL. The scan result
            # has already been produced; do not convert it into a scanner error.
            pass


def _codeql_preflight(language: str) -> tuple[bool, str]:
    if not shutil.which("codeql"):
        return False, "codeql executable not found on PATH"
    if language == "javascript-typescript" and not shutil.which("node"):
        return False, "node executable not found on PATH; required for CodeQL JavaScript/TypeScript extraction"
    return True, ""

DEFAULT_QUERY_SUITES = {
    "python": "codeql/python-queries:codeql-suites/python-security-extended.qls",
    "javascript-typescript": "codeql/javascript-queries:codeql-suites/javascript-security-extended.qls",
    "ruby": "codeql/ruby-queries:codeql-suites/ruby-security-extended.qls",
    "go": "codeql/go-queries:codeql-suites/go-security-extended.qls",
    "csharp": "codeql/csharp-queries:codeql-suites/csharp-security-extended.qls",
    "java-kotlin": "codeql/java-queries:codeql-suites/java-security-extended.qls",
    "c-cpp": "codeql/cpp-queries:codeql-suites/cpp-security-extended.qls",
}


def codeql_languages_for_files(files: Iterable[dict[str, Any]]) -> list[str]:
    names = [_norm_path(f.get("filename")) for f in files]
    detected: list[str] = []
    for language, extensions in CODEQL_LANGUAGE_EXTENSIONS.items():
        if any(name.endswith(extensions) for name in names):
            detected.append(language)
    return detected


def has_codeql_source_changes(files: list[dict[str, Any]]) -> bool:
    return bool(codeql_languages_for_files(files))


def has_python_source_changes(files: list[dict[str, Any]]) -> bool:
    return "python" in codeql_languages_for_files(files)


def default_query_suite_for_language(language: str) -> str | None:
    return DEFAULT_QUERY_SUITES.get(language)


def added_line_numbers_by_file(files: list[dict[str, Any]]) -> dict[str, set[int]]:
    """Parse unified diff hunks into added/new-side line numbers per file."""
    result: dict[str, set[int]] = {}
    for f in files:
        filename = _norm_path(f.get("filename"))
        patch = f.get("patch") or ""
        if not filename or not patch:
            continue
        added: set[int] = set()
        new_line: int | None = None
        for line in patch.splitlines():
            if line.startswith("@@"):
                # Example: @@ -10,7 +10,9 @@
                marker = line.split("@@", 2)[1]
                plus = next((part for part in marker.split() if part.startswith("+")), None)
                if plus:
                    start = plus[1:].split(",", 1)[0]
                    try:
                        new_line = int(start)
                    except ValueError:
                        new_line = None
                continue
            if new_line is None:
                continue
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                added.add(new_line)
                new_line += 1
            elif line.startswith("-"):
                # Removed line; no movement on new/head side.
                continue
            else:
                new_line += 1
        if added:
            result[filename] = added
    return result


def _sarif_location_tuple(location: dict[str, Any]) -> tuple[str | None, int | None]:
    phys = location.get("physicalLocation") or {}
    artifact = (phys.get("artifactLocation") or {}).get("uri")
    region = phys.get("region") or {}
    line = region.get("startLine")
    try:
        line = int(line) if line is not None else None
    except (TypeError, ValueError):
        line = None
    return _norm_path(artifact), line


def _extract_all_locations(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Return primary, related, and data-flow locations from one SARIF result."""
    out: list[dict[str, Any]] = []
    for loc in result.get("locations") or []:
        path, line = _sarif_location_tuple(loc)
        if path:
            out.append({"file": path, "line": line, "kind": "primary"})
    for loc in result.get("relatedLocations") or []:
        path, line = _sarif_location_tuple(loc)
        if path:
            out.append({"file": path, "line": line, "kind": "related"})
    for code_flow in result.get("codeFlows") or []:
        for thread_flow in code_flow.get("threadFlows") or []:
            for loc_wrap in thread_flow.get("locations") or []:
                loc = loc_wrap.get("location") or {}
                path, line = _sarif_location_tuple(loc)
                if path:
                    out.append({"file": path, "line": line, "kind": "codeflow"})
    # Deduplicate while preserving order.
    seen: set[tuple[str, int | None, str]] = set()
    deduped: list[dict[str, Any]] = []
    for loc in out:
        key = (loc.get("file"), loc.get("line"), loc.get("kind"))
        if key not in seen:
            seen.add(key)
            deduped.append(loc)
    return deduped


def finding_touches_added_lines(finding: dict[str, Any], added_lines: dict[str, set[int]]) -> bool:
    """Only promote CodeQL findings linked to the PR diff.

    A finding is linked when its primary/related/code-flow location intersects an
    added line in a changed file. Project-wide findings outside the PR diff are
    kept out of downstream vulnerability candidates.
    """
    locations = finding.get("locations") or []
    if not locations:
        file = _norm_path(finding.get("file"))
        line = finding.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        locations = [{"file": file, "line": line, "kind": "primary"}]
    for loc in locations:
        file = _norm_path(loc.get("file"))
        line = loc.get("line")
        try:
            line = int(line) if line is not None else None
        except (TypeError, ValueError):
            line = None
        if file in added_lines and line in added_lines[file]:
            return True
    return False


def filter_findings_to_pr_delta(findings: list[dict[str, Any]], files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    added_lines = added_line_numbers_by_file(files)
    filtered = []
    for f in findings:
        if finding_touches_added_lines(f, added_lines):
            enriched = dict(f)
            enriched["diff_linked"] = True
            filtered.append(enriched)
    return filtered



def _cmd_error_meta(label: str, cmd: list[str], result: dict[str, object]) -> dict[str, str]:
    stdout = str(result.get("stdout", "") or "")
    stderr = str(result.get("stderr", "") or "")
    rc = result.get("returncode")
    return {
        "status": "error",
        "stdout": stdout[-5000:],
        "stderr": (
            f"{label} failed; returncode={rc}\n"
            f"COMMAND: {' '.join(map(str, cmd))}\n"
            f"--- STDOUT TAIL ---\n{stdout[-3000:]}\n"
            f"--- STDERR TAIL ---\n{stderr[-5000:]}"
        )[-5000:],
    }


def scan_snapshot_with_codeql(repo_url: str, sha: str, language: str = "python", build_mode: str = "none", query_suite: str | None = None, timeout_seconds: int = 600) -> tuple[list[dict[str, Any]], dict[str, str]]:
    codeql_ram_mb = int(os.getenv("CODEQL_RAM_MB", "4096") or "4096")
    codeql_threads = int(os.getenv("CODEQL_THREADS", "1") or "1")
    # Static snapshot scan. For Python/JS/TS, --build-mode none avoids executing builds/tests.
    ok, preflight_error = _codeql_preflight(language)
    if not ok:
        return [], {"status": "tool_missing", "stdout": "", "stderr": preflight_error}
    with _codeql_tempdir() as root:
        clone = run_cmd(["git", "clone", "--depth", "1", repo_url, "repo"], cwd=root, timeout=min(timeout_seconds, 300))
        if not clone.get("ok"):
            return [], _cmd_error_meta("git clone", ["git", "clone", "--depth", "1", repo_url, "repo"], clone)
        repo_dir = root / "repo"
        # Fetch target sha if shallow clone does not include it.
        run_cmd(["git", "fetch", "--depth", "1", "origin", sha], cwd=repo_dir, timeout=min(timeout_seconds, 300))
        checkout = run_cmd(["git", "checkout", sha], cwd=repo_dir, timeout=min(timeout_seconds, 120))
        if not checkout.get("ok"):
            return [], _cmd_error_meta("git checkout", ["git", "checkout", sha], checkout)
        db_dir = root / "codeql-db"
        sarif = root / "results.sarif"
        create_cmd = ["codeql", "database", "create", str(db_dir), f"--language={language}", f"--source-root={repo_dir}", f"--ram={codeql_ram_mb}", f"--threads={codeql_threads}"]
        if build_mode == "none" and language in ["python", "javascript-typescript", "ruby"]:
            create_cmd.append("--build-mode=none")
        create = run_cmd(create_cmd, timeout=timeout_seconds)
        if create.get("returncode") == 124:
            return [], {"status": "timeout", "stdout": create.get("stdout", ""), "stderr": f"CodeQL database creation timed out after {timeout_seconds} seconds"}
        if not create.get("ok"):
            return [], _cmd_error_meta("CodeQL database create", create_cmd, create)
        analyze_cmd = ["codeql", "database", "analyze", str(db_dir)]
        if query_suite:
            analyze_cmd.append(query_suite)
        analyze_cmd.extend(["--format=sarif-latest", f"--output={sarif}", f"--ram={codeql_ram_mb}", f"--threads={codeql_threads}"])
        analyze = run_cmd(analyze_cmd, timeout=timeout_seconds)
        if analyze.get("returncode") == 124:
            return [], {"status": "timeout", "stdout": analyze.get("stdout", ""), "stderr": f"CodeQL analysis timed out after {timeout_seconds} seconds"}
        if not analyze.get("ok"):
            return [], _cmd_error_meta("CodeQL database analyze", analyze_cmd, analyze)
        data = parse_json_maybe(sarif.read_text(encoding="utf-8", errors="ignore")) if sarif.exists() else None
        findings = []
        if isinstance(data, dict):
            rules = {}
            for run in data.get("runs", []) or []:
                for r in (run.get("tool", {}).get("driver", {}).get("rules", []) or []):
                    rules[r.get("id")] = r
                for res in run.get("results", []) or []:
                    loc = (((res.get("locations") or [{}])[0]).get("physicalLocation") or {})
                    artifact = (loc.get("artifactLocation") or {}).get("uri")
                    region = loc.get("region") or {}
                    rule_id = res.get("ruleId")
                    rule = rules.get(rule_id, {})
                    tags = (rule.get("properties") or {}).get("tags", []) or []
                    cwe = ",".join([t for t in tags if str(t).lower().startswith("external/cwe") or str(t).lower().startswith("cwe")])
                    finding = {
                        "file": _norm_path(artifact),
                        "line": region.get("startLine"),
                        "rule": rule_id,
                        "severity": (rule.get("properties") or {}).get("problem.severity") or res.get("level"),
                        "cwe": cwe,
                        "description": (res.get("message") or {}).get("text") or rule.get("shortDescription", {}).get("text") or "CodeQL finding",
                        "locations": _extract_all_locations(res),
                        "raw": res,
                    }
                    findings.append(finding)
        return findings, {"status": "ok", "stdout": analyze.get("stdout", ""), "stderr": analyze.get("stderr", "")}


def diff_findings(base: list[dict[str, Any]], head: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Do not include line number in the key: small edits can shift existing alerts.
    # A finding is promoted later only if its SARIF locations intersect added lines.
    base_keys = {(f.get("rule"), _norm_path(f.get("file")), f.get("description")) for f in base}
    return [f for f in head if (f.get("rule"), _norm_path(f.get("file")), f.get("description")) not in base_keys]
