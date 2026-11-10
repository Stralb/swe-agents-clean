from __future__ import annotations

import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.scanners.dependency_diff import is_dependency_file
from src.utils.shell import parse_json_maybe, run_cmd


def _dependency_paths(
    files: list[dict[str, Any]],
) -> list[str]:
    paths: list[str] = []

    for file in files:
        path = str(
            file.get("filename")
            or file.get("path")
            or ""
        ).replace("\\", "/").lstrip("/")

        if path and is_dependency_file(path):
            paths.append(path)

    return sorted(set(paths))


def _normalise_target(
    target: Any,
    root: Path,
) -> str:
    value = str(target or "").replace("\\", "/")

    if not value:
        return ""

    try:
        candidate = Path(value)

        if candidate.is_absolute():
            return str(
                candidate.resolve().relative_to(
                    root.resolve()
                )
            ).replace("\\", "/")
    except Exception:
        pass

    while value.startswith("./"):
        value = value[2:]

    return value.lstrip("/")


def _advisory_ids(
    finding: dict[str, Any],
) -> tuple[str, ...]:
    identifiers: set[str] = set()

    for key in (
        "vuln_id",
        "VulnerabilityID",
        "id",
    ):
        value = finding.get(key)

        if value:
            identifiers.add(str(value))

    raw = finding.get("raw") or {}

    if isinstance(raw, dict):
        for key in (
            "VulnerabilityID",
            "ID",
        ):
            value = raw.get(key)

            if value:
                identifiers.add(str(value))

        for key in (
            "Aliases",
            "aliases",
        ):
            values = raw.get(key) or []

            if isinstance(values, str):
                identifiers.add(values)
            elif isinstance(values, list):
                identifiers.update(
                    str(value)
                    for value in values
                    if value
                )

    return tuple(sorted(identifiers))


def _finding_locator(
    finding: dict[str, Any],
) -> tuple[str, str, str]:
    return (
        str(
            finding.get("file")
            or ""
        ).replace("\\", "/").lower(),
        str(
            finding.get("package")
            or ""
        ).lower(),
        str(
            finding.get("package_path")
            or ""
        ).replace("\\", "/").lower(),
    )


def _parse_report(
    report: dict[str, Any],
    root: Path,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    for result in report.get("Results", []) or []:
        target = _normalise_target(
            result.get("Target"),
            root,
        )

        result_type = str(
            result.get("Type")
            or ""
        )

        result_class = str(
            result.get("Class")
            or ""
        )

        for vulnerability in (
            result.get("Vulnerabilities", [])
            or []
        ):
            vulnerability_id = str(
                vulnerability.get("VulnerabilityID")
                or ""
            )

            package = str(
                vulnerability.get("PkgName")
                or ""
            )

            installed_version = str(
                vulnerability.get("InstalledVersion")
                or ""
            )

            fixed_version = str(
                vulnerability.get("FixedVersion")
                or ""
            )

            severity = str(
                vulnerability.get("Severity")
                or "UNKNOWN"
            ).lower()

            cwe_ids = vulnerability.get("CweIDs") or []

            if isinstance(cwe_ids, str):
                cwe_ids = [cwe_ids]

            description = (
                vulnerability.get("Title")
                or vulnerability.get("Description")
                or "Known vulnerable dependency"
            )

            finding = {
                "file": target,
                "package": package,
                "package_path": (
                    vulnerability.get("PkgPath")
                    or ""
                ),
                "version": installed_version,
                "fixed_version": fixed_version,
                "vuln_id": vulnerability_id,
                "severity": severity,
                "cwe": ", ".join(
                    str(value)
                    for value in cwe_ids
                    if value
                ),
                "description": description,
                "result_type": result_type,
                "result_class": result_class,
                "primary_url": (
                    vulnerability.get("PrimaryURL")
                    or ""
                ),
                "references": (
                    vulnerability.get("References")
                    or []
                ),
                "raw": vulnerability,
            }

            finding["advisory_ids"] = list(
                _advisory_ids(finding)
            )

            finding["evidence"] = json.dumps(
                {
                    "package": package,
                    "version": installed_version,
                    "fixed_version": fixed_version,
                    "vulnerability": vulnerability_id,
                    "target": target,
                    "result_type": result_type,
                },
                sort_keys=True,
            )

            findings.append(finding)

    return findings


def _snapshot_delta_findings(
    base_findings: list[dict[str, Any]],
    head_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    base_by_locator: dict[
        tuple[str, str, str],
        list[set[str]],
    ] = defaultdict(list)

    for finding in base_findings:
        base_by_locator[
            _finding_locator(finding)
        ].append(
            set(_advisory_ids(finding))
        )

    introduced: list[dict[str, Any]] = []

    for finding in head_findings:
        locator = _finding_locator(finding)
        head_ids = set(_advisory_ids(finding))
        base_families = base_by_locator.get(
            locator,
            [],
        )

        present_in_base = any(
            bool(head_ids.intersection(base_ids))
            for base_ids in base_families
        )

        if present_in_base:
            continue

        enriched = dict(finding)
        enriched["change_type"] = (
            "introduced_vulnerable_dependency"
        )
        enriched["diff_linked"] = True
        enriched["introduced"] = True
        enriched["scanner"] = "trivy"

        introduced.append(enriched)

    return introduced


def _trivy_json_dict(value) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    if value in (None, ""):
        return {}

    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}

    if isinstance(parsed, dict):
        return parsed

    return {}


def _trivy_normalise_path(value: Any) -> str:
    return (
        str(value or "")
        .strip()
        .replace("\\", "/")
        .lstrip("./")
    )


def _trivy_paths_equal(
    first: Any,
    second: Any,
) -> bool:
    left = _trivy_normalise_path(first)
    right = _trivy_normalise_path(second)

    if not left or not right:
        return False

    return (
        left == right
        or left.endswith("/" + right)
        or right.endswith("/" + left)
    )


def _trivy_finding_target(
    finding: dict[str, Any],
) -> str:
    evidence = _trivy_json_dict(
        finding.get("evidence")
    )

    raw = _trivy_json_dict(
        finding.get("raw_json")
    )

    return _trivy_normalise_path(
        evidence.get("target")
        or finding.get("file_path")
        or raw.get("Target")
        or raw.get("target")
    )


def _trivy_target_changed_by_pr(
    target: Any,
    changed_dependency_paths: list[str],
) -> bool:
    return any(
        _trivy_paths_equal(
            target,
            changed_path,
        )
        for changed_path
        in changed_dependency_paths
    )


def _introduced_findings(
    base_findings: list[dict[str, Any]],
    head_findings: list[dict[str, Any]],
    changed_dependency_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    snapshot_delta = (
        _snapshot_delta_findings(
            base_findings,
            head_findings,
        )
    )

    changed_paths = [
        _trivy_normalise_path(path)
        for path in (
            changed_dependency_paths
            or []
        )
        if _trivy_normalise_path(path)
    ]

    attributable = []

    for finding in snapshot_delta:
        enriched = dict(finding)

        target = _trivy_finding_target(
            enriched
        )

        target_changed = (
            _trivy_target_changed_by_pr(
                target,
                changed_paths,
            )
        )

        evidence = _trivy_json_dict(
            enriched.get("evidence")
        )

        evidence.update({
            "snapshot_delta":
                True,
            "pr_attributable":
                bool(target_changed),
            "attribution_reason": (
                "target_changed_by_pr"
                if target_changed
                else (
                    "snapshot_delta_target_"
                    "not_changed_by_pr"
                )
            ),
            "changed_dependency_paths":
                changed_paths,
            "target":
                target,
        })

        enriched["evidence"] = evidence
        enriched["introduced"] = (
            1
            if target_changed
            else 0
        )
        enriched["diff_linked"] = (
            bool(target_changed)
        )

        if target_changed:
            attributable.append(enriched)

    return attributable


def _attach_trivy_package_locations(
    findings: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    stdout = metadata.get("stdout")

    if isinstance(stdout, dict):
        payload = stdout
    else:
        try:
            payload = json.loads(
                str(stdout or "{}")
            )
        except Exception:
            return findings

    report = payload.get("report")

    if not isinstance(report, dict):
        return findings

    results = report.get("Results")

    if not isinstance(results, list):
        return findings

    locations: dict[
        tuple[str, str, str],
        tuple[int, int],
    ] = {}

    for result in results:
        if not isinstance(result, dict):
            continue

        target = _trivy_normalise_path(
            result.get("Target")
        )

        packages = result.get("Packages")

        if not isinstance(packages, list):
            continue

        for package in packages:
            if not isinstance(package, dict):
                continue

            name = str(
                package.get("Name")
                or ""
            )

            version = str(
                package.get("Version")
                or ""
            )

            package_locations = (
                package.get("Locations")
            )

            if (
                not target
                or not name
                or not version
                or not isinstance(
                    package_locations,
                    list,
                )
                or not package_locations
            ):
                continue

            location = package_locations[0]

            if not isinstance(location, dict):
                continue

            try:
                start_line = int(
                    location.get("StartLine")
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                start_line = 0

            try:
                end_line = int(
                    location.get("EndLine")
                    or start_line
                )
            except (
                TypeError,
                ValueError,
            ):
                end_line = start_line

            if start_line <= 0:
                continue

            locations[
                (
                    target,
                    name,
                    version,
                )
            ] = (
                start_line,
                max(
                    start_line,
                    end_line,
                ),
            )

    enriched_findings = []

    for finding in findings:
        enriched = dict(finding)

        evidence = _trivy_json_dict(
            enriched.get("evidence")
        )

        raw = _trivy_json_dict(
            enriched.get("raw_json")
        )

        target = _trivy_normalise_path(
            evidence.get("target")
            or enriched.get("file_path")
            or raw.get("Target")
        )

        package = str(
            evidence.get("package")
            or raw.get("PkgName")
            or raw.get("PackageName")
            or ""
        )

        version = str(
            evidence.get("version")
            or raw.get("InstalledVersion")
            or raw.get("Version")
            or ""
        )

        location = locations.get(
            (
                target,
                package,
                version,
            )
        )

        if location is not None:
            start_line, end_line = location

            enriched["line"] = start_line
            enriched["start_line"] = (
                start_line
            )
            enriched["end_line"] = (
                end_line
            )

            evidence.update({
                "line":
                    start_line,
                "start_line":
                    start_line,
                "end_line":
                    end_line,
                "location_source":
                    "trivy_package_inventory",
            })

            raw["TrivyPackageLocation"] = {
                "StartLine": start_line,
                "EndLine": end_line,
            }

            enriched["evidence"] = evidence
            enriched["raw_json"] = raw

        enriched_findings.append(enriched)

    return enriched_findings



def _command_failure_meta(
    stage: str,
    output: dict[str, Any],
) -> dict[str, str]:
    returncode = int(
        output.get("returncode")
        or 0
    )

    status = (
        "timeout"
        if returncode == 124
        else "error"
    )

    return {
        "status": status,
        "stdout": json.dumps(
            {
                "stage": stage,
                "returncode": returncode,
                "stdout": (
                    output.get("stdout")
                    or ""
                ),
            }
        ),
        "stderr": str(
            output.get("stderr")
            or f"{stage} failed"
        ),
    }


def _scan_snapshot(
    root: Path,
    sha: str,
    changed_dependency_paths: list[str],
    trivy_version: str,
    *,
    timeout_seconds: int,
) -> tuple[
    list[dict[str, Any]],
    dict[str, str],
]:
    output = run_cmd(
        [
            "trivy",
            "filesystem",
            "--scanners",
            "vuln",
            "--pkg-types",
            "library",
            "--include-dev-deps",
            "--offline-scan",
            "--format",
            "json",
            "--no-progress",
            "--exit-code",
            "0",
            str(root),
        ],
        timeout=timeout_seconds,
    )

    stdout = str(
        output.get("stdout")
        or ""
    )

    stderr = str(
        output.get("stderr")
        or ""
    )

    report = parse_json_maybe(stdout)

    if int(output.get("returncode") or 0) == 124:
        status = "timeout"
        findings: list[dict[str, Any]] = []
    elif not isinstance(report, dict):
        status = (
            "parse_failed"
            if output.get("ok")
            else "error"
        )
        findings = []
    else:
        findings = _parse_report(
            report,
            root,
        )

        results = report.get("Results", []) or []

        status = (
            "ok"
            if results
            else "ok_with_warnings"
        )

    stored_report = {
        "sha": sha,
        "trivy_version": trivy_version,
        "changed_dependency_paths": (
            changed_dependency_paths
        ),
        "finding_count": len(findings),
        "result_count": (
            len(report.get("Results", []) or [])
            if isinstance(report, dict)
            else None
        ),
        "report": (
            report
            if isinstance(report, dict)
            else None
        ),
        "raw_stdout": (
            None
            if isinstance(report, dict)
            else stdout
        ),
    }

    if (
        status == "ok_with_warnings"
        and not stderr.strip()
    ):
        stderr = (
            "Trivy completed but returned no "
            "dependency result targets."
        )

    return findings, {
        "status": status,
        "stdout": json.dumps(
            stored_report,
            ensure_ascii=False,
        ),
        "stderr": stderr,
    }


def _combined_status(
    base_status: str,
    head_status: str,
) -> str:
    statuses = {
        base_status,
        head_status,
    }

    for blocking in (
        "tool_missing",
        "timeout",
        "parse_failed",
        "error",
    ):
        if blocking in statuses:
            return blocking

    if statuses == {"not_applicable"}:
        return "not_applicable"

    if "ok_with_warnings" in statuses:
        return "ok_with_warnings"

    return "ok"


def scan_dependency_snapshots_with_trivy(
    repo_url: str,
    base_sha: str,
    head_sha: str,
    files: list[dict[str, Any]],
    *,
    timeout_seconds: int = 600,
) -> tuple[
    list[dict[str, Any]],
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    """Compare complete base/head repository snapshots with Trivy."""

    dependency_paths = _dependency_paths(
        files
    )

    if not dependency_paths:
        meta = {
            "status": "not_applicable",
            "stdout": json.dumps({
                "changed_dependency_paths": [],
            }),
            "stderr": (
                "No dependency manifest or "
                "lockfile changed."
            ),
        }

        return [], dict(meta), dict(meta), dict(meta)

    missing_tools = [
        tool
        for tool in ("git", "trivy")
        if shutil.which(tool) is None
    ]

    if missing_tools:
        meta = {
            "status": "tool_missing",
            "stdout": "",
            "stderr": (
                "Missing required tool(s): "
                + ", ".join(missing_tools)
            ),
        }

        return [], dict(meta), dict(meta), dict(meta)

    version_output = run_cmd(
        ["trivy", "--version"],
        timeout=60,
    )

    trivy_version = str(
        version_output.get("stdout")
        or version_output.get("stderr")
        or ""
    ).strip()

    with tempfile.TemporaryDirectory() as temp:
        workspace = Path(temp)
        repo_dir = workspace / "repo"
        base_dir = workspace / "base"
        head_dir = workspace / "head"

        clone = run_cmd(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--no-checkout",
                repo_url,
                str(repo_dir),
            ],
            timeout=min(timeout_seconds, 300),
        )

        if not clone.get("ok"):
            meta = _command_failure_meta(
                "git clone",
                clone,
            )

            return [], dict(meta), dict(meta), dict(meta)

        for label, sha in (
            ("base", base_sha),
            ("head", head_sha),
        ):
            fetch = run_cmd(
                [
                    "git",
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    sha,
                ],
                cwd=repo_dir,
                timeout=min(timeout_seconds, 300),
            )

            if not fetch.get("ok"):
                meta = _command_failure_meta(
                    f"git fetch {label}",
                    fetch,
                )

                return [], dict(meta), dict(meta), dict(meta)

        for label, sha, target in (
            ("base", base_sha, base_dir),
            ("head", head_sha, head_dir),
        ):
            checkout = run_cmd(
                [
                    "git",
                    "worktree",
                    "add",
                    "--detach",
                    "--force",
                    str(target),
                    sha,
                ],
                cwd=repo_dir,
                timeout=min(timeout_seconds, 300),
            )

            if not checkout.get("ok"):
                meta = _command_failure_meta(
                    f"git worktree {label}",
                    checkout,
                )

                return [], dict(meta), dict(meta), dict(meta)

        base_findings, base_meta = _scan_snapshot(
            base_dir,
            base_sha,
            dependency_paths,
            trivy_version,
            timeout_seconds=timeout_seconds,
        )

        head_findings, head_meta = _scan_snapshot(
            head_dir,
            head_sha,
            dependency_paths,
            trivy_version,
            timeout_seconds=timeout_seconds,
        )

        base_findings = (
            _attach_trivy_package_locations(
                base_findings,
                base_meta,
            )
        )

        head_findings = (
            _attach_trivy_package_locations(
                head_findings,
                head_meta,
            )
        )

        snapshot_delta = (
            _snapshot_delta_findings(
                base_findings,
                head_findings,
            )
        )

        introduced = _introduced_findings(
            base_findings,
            head_findings,
            dependency_paths,
        )

        summary_status = _combined_status(
            str(base_meta.get("status") or ""),
            str(head_meta.get("status") or ""),
        )

        summary_meta = {
            "status": summary_status,
            "stdout": json.dumps(
                {
                    "trivy_version": trivy_version,
                    "changed_dependency_paths": (
                        dependency_paths
                    ),
                    "base_findings": (
                        len(base_findings)
                    ),
                    "head_findings": (
                        len(head_findings)
                    ),
                    "introduced": len(introduced),
                    "base_status": (
                        base_meta.get("status")
                    ),
                    "head_status": (
                        head_meta.get("status")
                    ),
                },
                ensure_ascii=False,
            ),
            "stderr": "\n".join(
                part
                for part in (
                    (
                        "base: "
                        + str(base_meta.get("stderr") or "")
                    ).strip(),
                    (
                        "head: "
                        + str(head_meta.get("stderr") or "")
                    ).strip(),
                )
                if part not in {"base:", "head:"}
            ),
        }

        return (
            introduced,
            summary_meta,
            base_meta,
            head_meta,
        )
