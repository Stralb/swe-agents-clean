from __future__ import annotations

import re
from typing import Any

from packaging.version import InvalidVersion, Version

REQ_RE = re.compile(r"^([A-Za-z0-9_.\-/]+)\s*([=<>!~]{1,2})\s*([A-Za-z0-9_.\-*+!]+)")
PKG_JSON_RE = re.compile(r'"([A-Za-z0-9_.@/\-]+)"\s*:\s*"([~^<>*= ]*[0-9][^"]*)"')
DEP_FILES = (
    # Python
    "requirements.txt", "requirements-dev.txt", "requirements-test.txt", "dev-requirements.txt", "test-requirements.txt", "requirements.in",
    "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "pipfile.lock", "poetry.lock", "uv.lock", "pdm.lock",
    "environment.yml", "environment.yaml", "conda.yml", "conda.yaml", "tox.ini",

    # JavaScript / TypeScript / Node
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",

    # Ruby
    "gemfile", "gemfile.lock", "gems.rb", "gems.locked",

    # Go
    "go.mod", "go.sum",

    # Java / JVM
    "pom.xml", "build.gradle", "build.gradle.kts", "gradle.lockfile",

    # .NET
    "packages.config", "packages.lock.json", "global.json",

    # Rust / PHP
    "cargo.toml", "cargo.lock", "composer.json", "composer.lock",
)


def is_dependency_file(filename: str) -> bool:
    lower = (filename or "").lower()
    return any(lower.endswith(x) for x in DEP_FILES)


def _clean_ver(v: str) -> str:
    return re.sub(r"^[~^<>=! ]+", "", v).split(",")[0].strip().strip('"\'')


def _operator(v: str) -> str:
    m = re.match(r"^([~^<>=! ]+)", v.strip())
    return (m.group(1).strip() if m else "==") or "=="


def _parse_added_removed(patch: str) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    removed: dict[str, str] = {}
    added: dict[str, str] = {}
    removed_ops: dict[str, str] = {}
    added_ops: dict[str, str] = {}
    for line in (patch or "").splitlines():
        if not line or line[:3] in {"+++", "---"}:
            continue
        sign = line[0]
        if sign not in {"+", "-"}:
            continue
        body = line[1:].strip()
        m = REQ_RE.match(body)
        if m:
            name, op, ver = m.groups()
            target = added if sign == "+" else removed
            ops = added_ops if sign == "+" else removed_ops
            target[name.lower()] = _clean_ver(ver)
            ops[name.lower()] = op
            continue
        for m2 in PKG_JSON_RE.finditer(body):
            name, raw_ver = m2.groups()
            target = added if sign == "+" else removed
            ops = added_ops if sign == "+" else removed_ops
            target[name.lower()] = _clean_ver(raw_ver)
            ops[name.lower()] = _operator(raw_ver)
    return removed, added, removed_ops, added_ops



def _added_dependency_line_map(patch: str) -> dict[str, int]:
    """Map package names to new-side line numbers for added dependency lines."""
    line_map: dict[str, int] = {}
    new_line: int | None = None
    for line in (patch or "").splitlines():
        if line.startswith("@@"):
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
            body = line[1:].strip()
            m = REQ_RE.match(body)
            if m:
                name, _, _ = m.groups()
                line_map.setdefault(name.lower(), new_line)
            else:
                for m2 in PKG_JSON_RE.finditer(body):
                    name, _ = m2.groups()
                    line_map.setdefault(name.lower(), new_line)
            new_line += 1
        elif line.startswith("-"):
            continue
        else:
            new_line += 1
    return line_map

def _is_widened_constraint(old_op: str, new_op: str, old_ver: str, new_ver: str) -> bool:
    # Simple, explainable heuristic: exact/pessimistic constraint changed to lower minimum or open minimum.
    try:
        old_v = Version(old_ver)
        new_v = Version(new_ver)
    except InvalidVersion:
        return False
    if old_op in {"==", "~=", ">="} and new_op in {">=", ">", ""} and new_v < old_v:
        return True
    if old_op == "==" and new_op in {">=", ">", "~="}:
        return True
    return False


def detect_dependency_changes(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch") or ""
        if not is_dependency_file(filename) or not patch:
            continue
        removed, added, removed_ops, added_ops = _parse_added_removed(patch)
        added_lines = _added_dependency_line_map(patch)

        for pkg, new_ver in added.items():
            old_ver = removed.get(pkg)
            if old_ver is None:
                findings.append({
                    "file": filename,
                    "package": pkg,
                    "new_version": new_ver,
                    "change_type": "added_dependency",
                    "description": f"New dependency introduced: {pkg} {new_ver}",
                    "line": added_lines.get(pkg),
                })
                continue
            old_op = removed_ops.get(pkg, "==")
            new_op = added_ops.get(pkg, "==")
            try:
                old_v = Version(old_ver)
                new_v = Version(new_ver)
                if _is_widened_constraint(old_op, new_op, old_ver, new_ver):
                    findings.append({
                        "file": filename,
                        "package": pkg,
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "change_type": "constraint_widened",
                        "description": f"Dependency constraint widened: {pkg} {old_op}{old_ver} -> {new_op}{new_ver}",
                        "line": added_lines.get(pkg),
                    })
                elif new_v < old_v:
                    findings.append({
                        "file": filename,
                        "package": pkg,
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "change_type": "dependency_downgrade",
                        "description": f"Dependency downgrade: {pkg} {old_ver} -> {new_ver}",
                        "line": added_lines.get(pkg),
                    })
            except InvalidVersion:
                if old_op != new_op:
                    findings.append({
                        "file": filename,
                        "package": pkg,
                        "old_version": old_ver,
                        "new_version": new_ver,
                        "change_type": "constraint_changed",
                        "description": f"Dependency constraint changed: {pkg}",
                        "line": added_lines.get(pkg),
                    })
    return findings


def detect_dependency_regressions(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # For downstream signals, keep downgrade/constraint widening, not every added package.
    return [
        f for f in detect_dependency_changes(files)
        if f.get("change_type") in {"dependency_downgrade", "constraint_widened", "constraint_changed"}
    ]
