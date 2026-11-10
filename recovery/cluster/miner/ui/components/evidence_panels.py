from __future__ import annotations

import re

import json
from collections import Counter

import pandas as pd
import streamlit as st

from ui.components.badges import badge_row, json_tags
from ui.utils.rendering import render_diff, safe_markdown


def upstream_badges(row: dict) -> list[str]:
    badges = []
    if (row.get("issue_word_count") or 0) >= 150:
        badges.append("Long issue")
    if row.get("has_code_block") or row.get("has_inline_code"):
        badges.append("Code/reproduction artifact")
    if row.get("has_traceback_or_log"):
        badges.append("Traceback/log")
    if row.get("has_file_path") or row.get("has_function_or_class"):
        badges.append("File/function mention")
    if row.get("has_suggested_fix"):
        badges.append("Suggested fix")
    if row.get("has_dependency_or_version"):
        badges.append("Dependency/version mention")
    if row.get("has_ai_marker"):
        badges.append("AI marker")
    return badges


def _link_button(label: str, url: str | None) -> None:
    if url:
        st.link_button(label, url, width="stretch")


def render_upstream_panel(row: dict) -> None:
    title = row.get("issue_title") or "Untitled issue"
    url = row.get("issue_url")
    if url:
        st.markdown(f"### [Issue: {title}]({url})")
    else:
        st.markdown(f"### Issue: {title}")
    meta = []
    if row.get("issue_author"):
        meta.append(f"by `{row.get('issue_author')}`")
    if row.get("issue_created_at"):
        meta.append(f"created {row.get('issue_created_at')}")
    if row.get("issue_comments_count") is not None:
        meta.append(f"{row.get('issue_comments_count')} comments")
    if meta:
        st.caption(" · ".join(meta))
    badges = upstream_badges(row)
    try:
        feature_json = json.loads(row.get("feature_json") or "{}")
    except Exception:
        feature_json = {}
    rich_badges = []
    for key, label in (
        ("has_reproduction_steps", "Reproduction steps"),
        ("has_expected_actual", "Expected/actual"),
        ("has_failing_test_signal", "Failing test"),
        ("has_security_steering_signal", "Security wording"),
        ("has_ci_or_secret_steering_signal", "CI/secrets wording"),
        ("has_ai_text_signal", "AI text mention"),
    ):
        if feature_json.get(key):
            rich_badges.append(label)
    badge_row(badges + rich_badges)
    if feature_json:
        with st.expander("Upstream indicators", expanded=False):
            st.json(feature_json)
    st.markdown('<div class="evidence-card">', unsafe_allow_html=True)
    safe_markdown(row.get("issue_body"), max_chars=40000)
    st.markdown('</div>', unsafe_allow_html=True)

    if row.get("pr_body"):
        with st.expander("PR description", expanded=False):
            safe_markdown(row.get("pr_body"), max_chars=18000)


def _pretty_json(value: str | None) -> str:
    if not value:
        return ""
    try:
        return json.dumps(json.loads(value), indent=2, ensure_ascii=False)
    except Exception:
        return str(value)


def _finding_label(f: dict) -> str:
    signal = str(f.get("finding_type") or "finding").replace("_", " ").title()
    scanner = str(f.get("scanner") or "scanner")
    rule = f.get("rule_id") or f.get("cwe") or ""
    loc = f.get("file_path") or ""
    if f.get("line"):
        loc += f":{f.get('line')}"
    return " · ".join(x for x in (signal, scanner, rule, loc) if x)



def _status_badge_text(status: str | None) -> str:
    value = str(status or "unknown")
    icons = {
        "ok": "✅",
        "finding": "🚩",
        "not_applicable": "⚪",
        "pending": "⏳",
        "retry": "🔁",
        "running": "🟦",
        "partial": "⚠️",
        "error": "❌",
        "timeout": "⏱️",
    }
    return f"{icons.get(value, '•')} {value}"


def _inline_integer(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _inline_json_value(value):
    if isinstance(value, (dict, list)):
        return value

    if value in (None, ""):
        return {}

    text = str(value).strip()

    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        return value


def _inline_json_dict(value) -> dict:
    parsed = _inline_json_value(value)

    if isinstance(parsed, dict):
        return parsed

    return {}


def _inline_scanner_name(value) -> str:
    scanner = (
        str(value or "")
        .strip()
        .lower()
        .replace("_", "-")
    )

    aliases = {
        "codeql-security": "codeql",
        "semgrep-source": "semgrep",
        "secret-ci": "gitleaks",
        "dependency-downgrade":
            "dependency-diff",
        "osv": "osv-scanner",
        "trivy-scanner": "trivy",
    }

    return aliases.get(
        scanner,
        scanner,
    )


def _inline_scanner_label(value) -> str:
    scanner = _inline_scanner_name(
        value
    )

    return {
        "codeql": "CodeQL",
        "semgrep": "Semgrep",
        "gitleaks": "Gitleaks",
        "dependency-diff":
            "Dependency diff",
        "osv-scanner": "OSV",
        "trivy": "Trivy",
    }.get(
        scanner,
        scanner or "Unknown",
    )


def _normalise_inline_finding(
    finding: dict,
) -> dict:
    output = dict(finding)

    scanner = _inline_scanner_name(
        finding.get("scanner")
    )

    raw = _inline_json_dict(
        finding.get("raw_json")
    )

    evidence_value = _inline_json_value(
        finding.get("evidence")
    )

    evidence = (
        evidence_value
        if isinstance(
            evidence_value,
            dict,
        )
        else {}
    )

    file_path = str(
        finding.get("file_path")
        or ""
    ).strip()

    start_line = _inline_integer(
        finding.get("line")
    )

    end_line = start_line
    start_column = 0
    end_column = 0

    if scanner == "codeql":
        locations = (
            raw.get("locations")
            or []
        )

        if locations:
            primary = locations[0] or {}

            physical = (
                primary.get(
                    "physicalLocation"
                )
                or {}
            )

            artifact = (
                physical.get(
                    "artifactLocation"
                )
                or {}
            )

            region = (
                physical.get("region")
                or {}
            )

            file_path = (
                file_path
                or str(
                    artifact.get("uri")
                    or ""
                )
            )

            start_line = (
                start_line
                or _inline_integer(
                    region.get(
                        "startLine"
                    )
                )
            )

            end_line = (
                _inline_integer(
                    region.get("endLine")
                )
                or start_line
            )

            start_column = (
                _inline_integer(
                    region.get(
                        "startColumn"
                    )
                )
            )

            end_column = (
                _inline_integer(
                    region.get(
                        "endColumn"
                    )
                )
            )

    elif scanner == "semgrep":
        start = raw.get("start") or {}
        end = raw.get("end") or {}

        file_path = (
            file_path
            or str(
                raw.get("path")
                or ""
            )
        )

        start_line = (
            start_line
            or _inline_integer(
                start.get("line")
            )
        )

        end_line = (
            _inline_integer(
                end.get("line")
            )
            or start_line
        )

        start_column = (
            _inline_integer(
                start.get("col")
            )
        )

        end_column = (
            _inline_integer(
                end.get("col")
            )
        )

    elif scanner == "gitleaks":
        file_path = (
            file_path
            or str(
                raw.get("File")
                or ""
            )
        )

        start_line = (
            start_line
            or _inline_integer(
                raw.get("StartLine")
            )
        )

        end_line = (
            _inline_integer(
                raw.get("EndLine")
            )
            or start_line
        )

        start_column = (
            _inline_integer(
                raw.get("StartColumn")
            )
        )

        end_column = (
            _inline_integer(
                raw.get("EndColumn")
            )
        )

    elif scanner == "dependency-diff":
        file_path = (
            file_path
            or str(
                raw.get("file")
                or ""
            )
        )

        start_line = (
            start_line
            or _inline_integer(
                raw.get("line")
            )
        )

        end_line = start_line

    package = str(
        evidence.get("package")
        or ""
    )

    version = str(
        evidence.get("version")
        or evidence.get(
            "new_version"
        )
        or ""
    )

    old_version = str(
        evidence.get("old_version")
        or ""
    )

    fixed_version = str(
        evidence.get("fixed_version")
        or ""
    )

    identifier = str(
        finding.get("rule_id")
        or evidence.get("vuln_id")
        or evidence.get(
            "vulnerability"
        )
        or evidence.get(
            "change_type"
        )
        or finding.get(
            "finding_type"
        )
        or "finding"
    )

    context_parts = []

    for name in (
        "confidence",
        "impact",
        "likelihood",
    ):
        value = evidence.get(name)

        if value not in (
            None,
            "",
        ):
            context_parts.append(
                name + "=" + str(value)
            )

    if "promoted" in evidence:
        context_parts.append(
            "promoted="
            + str(
                bool(
                    evidence.get(
                        "promoted"
                    )
                )
            ).lower()
        )

    rejection_reasons = (
        evidence.get(
            "rejection_reasons"
        )
        or []
    )

    if rejection_reasons:
        context_parts.append(
            "rejection="
            + ", ".join(
                str(reason)
                for reason
                in rejection_reasons
            )
        )

    location_kind = (
        "Exact scanner line"
        if start_line > 0
        else (
            "Package/file level"
            if scanner in {
                "osv-scanner",
                "trivy",
            }
            or package
            else "File level"
        )
    )

    location_label = (
        file_path
        or "Unknown file"
    )

    if start_line > 0:
        location_label += (
            ":" + str(start_line)
        )

        if (
            end_line
            and end_line != start_line
        ):
            location_label += (
                "-" + str(end_line)
            )

        if start_column:
            location_label += (
                ":" + str(start_column)
            )

            if end_column:
                location_label += (
                    "-" + str(end_column)
                )

    introduced = _inline_integer(
        finding.get("introduced")
    )

    introduction_label = (
        "Scanner delta marked introduced"
        if introduced == 1
        else "Stored finding; not marked introduced"
    )

    output.update({
        "scanner":
            scanner,
        "scanner_label":
            _inline_scanner_label(
                scanner
            ),
        "file_path":
            file_path,
        "line":
            start_line,
        "start_line":
            start_line,
        "end_line":
            end_line or start_line,
        "start_column":
            start_column,
        "end_column":
            end_column,
        "identifier":
            identifier,
        "package":
            package,
        "version":
            version,
        "old_version":
            old_version,
        "fixed_version":
            fixed_version,
        "location_kind":
            location_kind,
        "location_label":
            location_label,
        "introduction_label":
            introduction_label,
        "triage_context":
            " · ".join(
                context_parts
            ),
        "evidence_parsed":
            evidence_value,
        "raw_parsed":
            raw,
    })

    return output


def _inline_normalise_path(value) -> str:
    return (
        str(value or "")
        .strip()
        .replace("\\", "/")
        .lstrip("./")
        .lower()
    )


def _inline_paths_match(
    left,
    right,
) -> bool:
    left_path = _inline_normalise_path(
        left
    )

    right_path = _inline_normalise_path(
        right
    )

    if not left_path or not right_path:
        return False

    return (
        left_path == right_path
        or left_path.endswith(
            "/" + right_path
        )
        or right_path.endswith(
            "/" + left_path
        )
    )


def _inline_patch_line_sets(
    patch,
) -> tuple[set[int], set[int]]:
    displayed: set[int] = set()
    added: set[int] = set()

    new_line = None

    for raw_line in str(
        patch or ""
    ).splitlines():
        hunk = re.match(
            r"^@@ -\d+(?:,\d+)? "
            r"\+(\d+)(?:,\d+)? @@",
            raw_line,
        )

        if hunk:
            new_line = int(
                hunk.group(1)
            )
            continue

        if new_line is None:
            continue

        if (
            raw_line.startswith("+++")
            or raw_line.startswith("---")
        ):
            continue

        if raw_line.startswith("+"):
            displayed.add(new_line)
            added.add(new_line)
            new_line += 1
            continue

        if raw_line.startswith("-"):
            continue

        if raw_line.startswith("\\"):
            continue

        displayed.add(new_line)
        new_line += 1

    return displayed, added



def _inline_patch_new_side_lines(
    patch,
) -> list[dict]:
    rows: list[dict] = []

    new_line = None

    for raw_line in str(
        patch or ""
    ).splitlines():
        hunk = re.match(
            r"^@@ -\d+(?:,\d+)? "
            r"\+(\d+)(?:,\d+)? @@",
            raw_line,
        )

        if hunk:
            new_line = int(
                hunk.group(1)
            )
            continue

        if new_line is None:
            continue

        if (
            raw_line.startswith("+++")
            or raw_line.startswith("---")
            or raw_line.startswith("diff --git")
        ):
            continue

        if raw_line.startswith("-"):
            continue

        if raw_line.startswith("\\"):
            continue

        added = raw_line.startswith("+")

        text = (
            raw_line[1:]
            if raw_line
            else ""
        )

        rows.append({
            "line": new_line,
            "text": text,
            "text_lower": text.lower(),
            "added": added,
        })

        new_line += 1

    return rows


def _inline_dependency_versions(
    finding: dict,
) -> list[str]:
    values = []

    for key in (
        "version",
        "old_version",
        "fixed_version",
    ):
        value = str(
            finding.get(key)
            or ""
        ).strip()

        if not value:
            continue

        variants = {
            value.lower(),
            value.lower().lstrip("v"),
            value.lower().lstrip("^~<>= "),
        }

        for variant in variants:
            if variant and variant not in values:
                values.append(variant)

    return values


def _inline_dependency_markers(
    package: str,
) -> list[tuple[str, int]]:
    package = package.strip().lower()

    if not package:
        return []

    markers = [
        ('"' + package + '"', 14),
        ("'" + package + "'", 14),
        ("node_modules/" + package, 16),
        ("/" + package + "@", 16),
        (package + "@", 13),
        (package + ":", 12),
        (package + "==", 16),
        (package + ">=", 15),
        (package + "<=", 15),
        (package + "~=", 15),
        (package + "=", 12),
        (">" + package + "<", 16),
        (package, 7),
    ]

    if package.startswith("@") and "/" in package:
        unscoped = package.split(
            "/",
            1,
        )[1]

        if len(unscoped) >= 4:
            markers.append(
                (
                    '"' + unscoped + '"',
                    6,
                )
            )

    unique = []
    seen = set()

    for marker, score in markers:
        if not marker or marker in seen:
            continue

        seen.add(marker)
        unique.append(
            (marker, score)
        )

    return unique


def _inline_infer_dependency_line(
    finding: dict,
    patch,
    filename: str,
) -> dict | None:
    if _inline_integer(
        finding.get("start_line")
        or finding.get("line")
    ) > 0:
        return None

    package = str(
        finding.get("package")
        or ""
    ).strip()

    if not package:
        return None

    rows = _inline_patch_new_side_lines(
        patch
    )

    if not rows:
        return None

    package_lower = package.lower()

    markers = _inline_dependency_markers(
        package
    )

    versions = _inline_dependency_versions(
        finding
    )

    candidates = []

    for index, row in enumerate(rows):
        text = row["text_lower"]
        score = 0
        matched_marker = ""

        for marker, marker_score in markers:
            if marker in text:
                if marker_score > score:
                    score = marker_score
                    matched_marker = marker

        if score <= 0:
            continue

        matched_versions = [
            version
            for version in versions
            if version in text
        ]

        if matched_versions:
            score += 7

        nearby_start = max(
            0,
            index - 6,
        )

        nearby_end = min(
            len(rows),
            index + 7,
        )

        nearby_rows = rows[
            nearby_start:nearby_end
        ]

        nearby_version = ""

        if not matched_versions:
            for nearby in nearby_rows:
                for version in versions:
                    if version in nearby[
                        "text_lower"
                    ]:
                        nearby_version = version
                        score += 4
                        break

                if nearby_version:
                    break

        filename_lower = str(
            filename or ""
        ).lower()

        if any(
            name in filename_lower
            for name in (
                "package-lock",
                "npm-shrinkwrap",
                "pnpm-lock",
                "yarn.lock",
                "package.json",
                "requirements",
                "poetry.lock",
                "pipfile",
                "go.mod",
                "go.sum",
                "pom.xml",
                "gradle",
                "cargo.lock",
                "cargo.toml",
                "composer.lock",
                "composer.json",
            )
        ):
            score += 3

        if row["added"]:
            score += 2

        candidates.append({
            "score": score,
            "line": row["line"],
            "added": row["added"],
            "marker": matched_marker,
            "version": (
                matched_versions[0]
                if matched_versions
                else nearby_version
            ),
            "text": row["text"],
        })

    if not candidates:
        return None

    candidates.sort(
        key=lambda candidate: (
            -candidate["score"],
            0
            if candidate["added"]
            else 1,
            candidate["line"],
        )
    )

    best = candidates[0]

    if int(best["score"]) < 10:
        return None

    reason_parts = [
        "package=" + package,
        "matched=" + str(
            best.get("marker")
            or package_lower
        ),
    ]

    if best.get("version"):
        reason_parts.append(
            "version="
            + str(best["version"])
        )

    reason_parts.append(
        "patch_line="
        + str(best["line"])
    )

    relation = (
        "Inferred on added line"
        if best["added"]
        else "Inferred on context line"
    )

    return {
        "line": int(best["line"]),
        "relation": relation,
        "reason": "; ".join(
            reason_parts
        ),
        "score": int(best["score"]),
        "line_text": str(
            best.get("text")
            or ""
        ),
    }

def _inline_diff_relation(
    finding: dict,
    patch,
) -> str:
    start = _inline_integer(
        finding.get("start_line")
        or finding.get("line")
    )

    end = (
        _inline_integer(
            finding.get("end_line")
        )
        or start
    )

    if start <= 0:
        return "Package/file level"

    if not patch:
        return "Exact line; no stored patch"

    displayed, added = (
        _inline_patch_line_sets(patch)
    )

    relevant = set(
        range(
            start,
            min(
                max(start, end),
                start + 500,
            )
            + 1,
        )
    )

    if relevant & added:
        return "On added line"

    if relevant & displayed:
        return "On context line"

    return "Outside stored patch"


def _inline_severity_rank(
    finding: dict,
) -> int:
    severity = str(
        finding.get("severity")
        or ""
    ).strip().lower()

    return {
        "critical": 5,
        "blocker": 5,
        "high": 4,
        "error": 4,
        "fatal": 4,
        "medium": 3,
        "moderate": 3,
        "warning": 3,
        "warn": 3,
        "low": 1,
        "info": 1,
        "informational": 1,
        "note": 1,
    }.get(severity, 2)

def render_downstream_panel(
    row: dict,
    files: list[dict],
    findings: list[dict],
    scanner_runs: list[dict] | None = None,
    scanner_jobs: list[dict] | None = None,
) -> None:
    findings = [
        _normalise_inline_finding(
            finding
        )
        for finding in findings
    ]

    findings.sort(
        key=lambda finding: (
            -_inline_severity_rank(finding),
            str(
                finding.get("scanner_label")
                or ""
            ),
            str(
                finding.get("file_path")
                or ""
            ),
            _inline_integer(
                finding.get("start_line")
                or finding.get("line")
            ),
            str(
                finding.get("identifier")
                or ""
            ),
        )
    )

    title = (
        row.get("pr_title")
        or "Untitled PR"
    )

    url = row.get("pr_url")

    if url:
        st.markdown(
            f"### [PR: {title}]({url})"
        )
    else:
        st.markdown(
            f"### PR: {title}"
        )

    st.caption(
        "State: "
        f"{row.get('pr_state')} - "
        "Merged: "
        f"{bool(row.get('pr_merged'))} - "
        "Author: "
        f"{row.get('pr_author') or 'unknown'}"
    )

    with st.expander(
        "Scanner execution and routing",
        expanded=False,
    ):
        st.markdown("#### Worker routing")

        if scanner_jobs:
            job_rows = []

            for job in scanner_jobs:
                job_rows.append({
                    "Worker":
                        job.get("job_type"),
                    "Job status":
                        _status_badge_text(
                            job.get("status")
                        ),
                    "Why it ran / not applicable":
                        job.get("route_reason")
                        or "scheduled",
                    "Last error":
                        job.get("last_error")
                        or "",
                })

            st.dataframe(
                pd.DataFrame(job_rows),
                hide_index=True,
                width="stretch",
            )
        else:
            st.caption(
                "No scanner jobs stored yet."
            )

        st.markdown("#### Scanner results")

        counts = Counter(
            (
                finding.get("scanner")
                or "unknown"
            )
            for finding in findings
        )

        if scanner_runs:
            run_rows = []

            for run in scanner_runs:
                scanner = (
                    run.get("scanner")
                    or "unknown"
                )

                run_rows.append({
                    "Scanner": scanner,
                    "Status":
                        run.get("status"),
                    "Findings":
                        counts.get(scanner, 0),
                })

            st.dataframe(
                pd.DataFrame(run_rows),
                hide_index=True,
                width="stretch",
            )

        elif findings:
            result_rows = [
                {
                    "Scanner": scanner,
                    "Status":
                        "finding stored",
                    "Findings": count,
                }
                for scanner, count
                in sorted(counts.items())
            ]

            st.dataframe(
                pd.DataFrame(result_rows),
                hide_index=True,
                width="stretch",
            )

        else:
            st.info(
                "No stored scanner findings "
                "exist for this case."
            )

    file_records = []

    for index, file_row in enumerate(files):
        record = dict(file_row)

        filename = str(
            record.get("filename")
            or "file"
        )

        patch = str(
            record.get("patch")
            or ""
        )

        matched = [
            finding
            for finding in findings
            if _inline_paths_match(
                finding.get("file_path"),
                filename,
            )
        ]

        for finding in matched:
            finding["location_source"] = (
                "scanner"
                if _inline_integer(
                    finding.get("start_line")
                    or finding.get("line")
                ) > 0
                else "package/file level"
            )

            inferred = (
                _inline_infer_dependency_line(
                    finding,
                    patch,
                    filename,
                )
            )

            if inferred is not None:
                inferred_line = int(
                    inferred["line"]
                )

                finding["line"] = (
                    inferred_line
                )

                finding["start_line"] = (
                    inferred_line
                )

                finding["end_line"] = (
                    inferred_line
                )

                finding["location_source"] = (
                    "inferred"
                )

                finding["location_kind"] = (
                    "Inferred dependency line"
                )

                finding["location_label"] = (
                    filename
                    + ":"
                    + str(inferred_line)
                    + " (inferred)"
                )

                finding["inference_reason"] = (
                    inferred["reason"]
                )

                finding["inference_score"] = (
                    inferred["score"]
                )

                finding["diff_relation"] = (
                    inferred["relation"]
                )

            else:
                finding["inference_reason"] = ""

                finding["diff_relation"] = (
                    _inline_diff_relation(
                        finding,
                        patch,
                    )
                )

        record["_index"] = index
        record["_filename"] = filename
        record["_patch"] = patch
        record["_patch_lines"] = len(
            patch.splitlines()
        )
        record["_findings"] = matched

        file_records.append(record)

    unmatched_findings = [
        finding
        for finding in findings
        if not any(
            _inline_paths_match(
                finding.get("file_path"),
                record.get("_filename"),
            )
            for record in file_records
        )
    ]

    finding_file_records = [
        record
        for record in file_records
        if record.get("_findings")
    ]

    st.markdown(
        "#### Finding-aware patch viewer"
    )

    st.caption(
        "Choose one changed file at a time. "
        "The complete stored patch is rendered with "
        "every scanner finding reported for that file. "
        "Exact findings outside the stored patch are "
        "listed separately rather than hidden."
    )

    summary_columns = st.columns(4)

    summary_columns[0].metric(
        "Changed files",
        len(file_records),
    )

    summary_columns[1].metric(
        "Files with findings",
        len(finding_file_records),
    )

    summary_columns[2].metric(
        "Case findings",
        len(findings),
    )

    summary_columns[3].metric(
        "Unmatched findings",
        len(unmatched_findings),
        help=(
            "Scanner paths that could not be matched "
            "to a changed-file record."
        ),
    )

    if not file_records:
        st.info(
            "No changed files are stored for this case."
        )

        if unmatched_findings:
            st.dataframe(
                pd.DataFrame([
                    {
                        "Scanner":
                            finding.get(
                                "scanner_label"
                            ),
                        "Identifier":
                            finding.get(
                                "identifier"
                            ),
                        "Reported location":
                            finding.get(
                                "location_label"
                            ),
                        "Description":
                            finding.get(
                                "description"
                            ),
                    }
                    for finding
                    in unmatched_findings
                ]),
                hide_index=True,
                width="stretch",
            )

        return

    case_key = str(
        row.get("id")
        or row.get("case_id")
        or row.get("pr_number")
        or row.get("pr_url")
        or "current"
    )

    if finding_file_records:
        scope = st.radio(
            "File scope",
            (
                "Files with findings",
                "All changed files",
            ),
            horizontal=True,
            key=(
                "downstream_file_scope_"
                + case_key
            ),
        )
    else:
        scope = "All changed files"

    selectable = (
        finding_file_records
        if scope == "Files with findings"
        else file_records
    )

    selectable = sorted(
        selectable,
        key=lambda record: (
            0
            if record.get("_findings")
            else 1,
            -len(
                record.get("_findings")
                or []
            ),
            record.get("_filename")
            or "",
        ),
    )

    labels = []
    label_to_record = {}

    for position, record in enumerate(
        selectable,
        start=1,
    ):
        finding_count = len(
            record.get("_findings")
            or []
        )

        patch_lines = int(
            record.get("_patch_lines")
            or 0
        )

        label = (
            f"{record.get('_filename')} - "
            f"{finding_count} finding(s) - "
            f"{patch_lines} stored patch line(s)"
        )

        if label in label_to_record:
            label = (
                label
                + f" - file {position}"
            )

        labels.append(label)
        label_to_record[label] = record

    selected_label = st.selectbox(
        "Patch file",
        labels,
        key=(
            "downstream_patch_file_"
            + case_key
        ),
    )

    selected = label_to_record[
        selected_label
    ]

    filename = str(
        selected.get("_filename")
        or "file"
    )

    patch = str(
        selected.get("_patch")
        or ""
    )

    selected_findings = list(
        selected.get("_findings")
        or []
    )

    exact_inline_findings = [
        finding
        for finding in selected_findings
        if finding.get("diff_relation")
        in {
            "On added line",
            "On context line",
        }
    ]

    inferred_inline_findings = [
        finding
        for finding in selected_findings
        if finding.get("diff_relation")
        in {
            "Inferred on added line",
            "Inferred on context line",
        }
    ]

    inline_findings = (
        exact_inline_findings
        + inferred_inline_findings
    )

    outside_findings = [
        finding
        for finding in selected_findings
        if finding.get("diff_relation")
        in {
            "Outside stored patch",
            "Exact line; no stored patch",
        }
    ]

    package_findings = [
        finding
        for finding in selected_findings
        if finding.get("diff_relation")
        == "Package/file level"
    ]

    file_metrics = st.columns(5)

    file_metrics[0].metric(
        "File findings",
        len(selected_findings),
    )

    file_metrics[1].metric(
        "Exact inline",
        len(exact_inline_findings),
        help=(
            "Locations supplied directly by "
            "the scanner."
        ),
    )

    file_metrics[2].metric(
        "Inferred inline",
        len(inferred_inline_findings),
        help=(
            "Package findings mapped to a manifest "
            "or lockfile line by package/version."
        ),
    )

    file_metrics[3].metric(
        "Outside patch",
        len(outside_findings),
    )

    file_metrics[4].metric(
        "Unresolved package-level",
        len(package_findings),
    )

    st.markdown(
        f"##### Findings for `{filename}`"
    )

    if selected_findings:
        finding_rows = []

        for finding in selected_findings:
            finding_rows.append({
                "Finding ID":
                    finding.get(
                        "finding_id"
                    ),
                "Scanner":
                    finding.get(
                        "scanner_label"
                    ),
                "Severity":
                    finding.get("severity")
                    or "Unranked",
                "Rule / CVE / GHSA":
                    finding.get(
                        "identifier"
                    ),
                "Exact location":
                    finding.get(
                        "location_label"
                    ),
                "Patch relation":
                    finding.get(
                        "diff_relation"
                    ),
                "Location source":
                    finding.get(
                        "location_source"
                    ),
                "Inference reason":
                    finding.get(
                        "inference_reason"
                    ),
                "Introduced flag":
                    (
                        "yes"
                        if _inline_integer(
                            finding.get(
                                "introduced"
                            )
                        ) == 1
                        else "no"
                    ),
                "Package":
                    finding.get("package"),
                "Version":
                    finding.get("version"),
                "Fixed version":
                    finding.get(
                        "fixed_version"
                    ),
                "Scanner context":
                    finding.get(
                        "triage_context"
                    ),
                "Description":
                    finding.get(
                        "description"
                    ),
            })

        st.dataframe(
            pd.DataFrame(finding_rows),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "No scanner findings are mapped "
            "to this changed file."
        )

    st.markdown(
        f"##### Complete stored patch - `{filename}`"
    )

    if patch:
        render_diff(
            patch,
            max_lines=None,
            file_path=filename,
            findings=selected_findings,
        )
    else:
        st.warning(
            "This changed file has no stored patch text."
        )

    if outside_findings:
        st.warning(
            f"{len(outside_findings)} exact finding(s) "
            "are reported for this file but fall "
            "outside the stored patch hunk."
        )

        st.dataframe(
            pd.DataFrame([
                {
                    "Finding ID":
                        finding.get(
                            "finding_id"
                        ),
                    "Scanner":
                        finding.get(
                            "scanner_label"
                        ),
                    "Severity":
                        finding.get("severity")
                        or "Unranked",
                    "Identifier":
                        finding.get(
                            "identifier"
                        ),
                    "Exact location":
                        finding.get(
                            "location_label"
                        ),
                    "Description":
                        finding.get(
                            "description"
                        ),
                }
                for finding in outside_findings
            ]),
            hide_index=True,
            width="stretch",
        )

    if package_findings:
        st.info(
            f"{len(package_findings)} package/file-level "
            "finding(s) could not be matched to a package "
            "entry in this stored patch. They remain "
            "visible without an invented line."
        )

    if selected_findings:
        with st.expander(
            "Scanner-native details for selected file",
            expanded=False,
        ):
            for finding in selected_findings:
                heading = (
                    f"{finding.get('scanner_label')} - "
                    f"{finding.get('identifier')} - "
                    f"{finding.get('location_label')}"
                )

                with st.container(border=True):
                    st.markdown(
                        f"**{heading}**"
                    )

                    if finding.get("description"):
                        st.write(
                            finding.get("description")
                        )

                    if finding.get("triage_context"):
                        st.caption(
                            finding.get(
                                "triage_context"
                            )
                        )

                    evidence = finding.get(
                        "evidence_parsed"
                    )

                    if evidence:
                        st.markdown(
                            "**Structured evidence**"
                        )

                        if isinstance(
                            evidence,
                            dict,
                        ):
                            st.json(evidence)
                        else:
                            st.code(
                                str(evidence)[:10000]
                            )

                    raw = _pretty_json(
                        finding.get("raw_json")
                    )

                    if raw:
                        with st.expander(
                            "Raw scanner JSON",
                            expanded=False,
                        ):
                            st.code(
                                raw[:30000],
                                language="json",
                            )

    if unmatched_findings:
        with st.expander(
            (
                "Findings not matched to a changed file "
                f"({len(unmatched_findings)})"
            ),
            expanded=False,
        ):
            st.dataframe(
                pd.DataFrame([
                    {
                        "Finding ID":
                            finding.get(
                                "finding_id"
                            ),
                        "Scanner":
                            finding.get(
                                "scanner_label"
                            ),
                        "Severity":
                            finding.get("severity")
                            or "Unranked",
                        "Identifier":
                            finding.get(
                                "identifier"
                            ),
                        "Reported location":
                            finding.get(
                                "location_label"
                            ),
                        "Description":
                            finding.get(
                                "description"
                            ),
                    }
                    for finding
                    in unmatched_findings
                ]),
                hide_index=True,
                width="stretch",
            )


def _manage_tags_modal(db) -> None:
    all_tags = db.query("SELECT id, name FROM tags WHERE type='manual' ORDER BY name")
    st.caption("Rename, delete, or add manual tags used across all cases.")
    if not all_tags:
        st.info("No global manual tags yet.")
    for t in all_tags:
        c1, c2, c3 = st.columns([4, 1, 1], gap="small")
        new_name = c1.text_input("Tag name", value=t["name"], key=f"rename_tag_{t['id']}", label_visibility="collapsed")
        if c2.button("Rename", key=f"rename_btn_{t['id']}", width="stretch") and new_name.strip():
            db.execute("UPDATE tags SET name=? WHERE id=?", (new_name.strip(), t["id"]))
            st.rerun()
        if c3.button("Delete", key=f"delete_tag_{t['id']}", width="stretch"):
            db.execute("DELETE FROM case_tags WHERE tag_id=?", (t["id"],))
            db.execute("DELETE FROM tags WHERE id=?", (t["id"],))
            st.rerun()
    st.divider()
    c_add1, c_add2 = st.columns([4, 1], gap="small")
    new_tag = c_add1.text_input("New global tag", key="new_global_tag", placeholder="e.g. needs-codeql")
    if c_add2.button("Add", width="stretch") and new_tag.strip():
        db.execute("INSERT OR IGNORE INTO tags(name, type) VALUES (?, 'manual')", (new_tag.strip(),))
        st.rerun()


if hasattr(st, "dialog"):
    @st.dialog("Manage global tags")
    def _manage_tags_dialog(db) -> None:
        _manage_tags_modal(db)
else:
    _manage_tags_dialog = None


def render_review_panel(row: dict, db, case_id: int | None = None) -> None:
    case_id = int(case_id or row["case_id"])
    st.markdown(
        """
<div class='decision-shell'>
  <div class='decision-title'>Decision</div>
  <div class='decision-help'>Assign your manual label, optional tags, and notes for this case.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    labels = [
        "Benign",
        "Tool false positive",
        "Benign security fix",
        "Security regression candidate",
        "Suspicious issue-linked regression",
        "High-confidence suspicious",
        "Unclear",
    ]
    current = row.get("final_label") or "Unclear"
    final = st.radio(
        "Manual label",
        labels,
        index=labels.index(current) if current in labels else labels.index("Unclear"),
        horizontal=False,
        help="Your final human judgement for this case.",
    )

    all_tags = db.query("SELECT id, name FROM tags WHERE type='manual' ORDER BY name")
    case_tags = db.query("SELECT t.id, t.name FROM case_tags ct JOIN tags t ON ct.tag_id=t.id WHERE ct.case_id=? ORDER BY t.name", (case_id,))
    current_tags = {t["name"] for t in case_tags}
    tag_names = [t["name"] for t in all_tags]

    c_tags, c_manage = st.columns([4, 1.35], gap="small", vertical_alignment="bottom")
    with c_tags:
        selected_tags = st.multiselect(
            "Case tags",
            options=tag_names,
            default=sorted(current_tags),
            help="Manual research tags assigned to this case.",
        )
    with c_manage:
        if st.button("Manage global tags", width="stretch"):
            if _manage_tags_dialog is not None:
                _manage_tags_dialog(db)
            else:
                st.session_state["show_global_tag_manager"] = not st.session_state.get("show_global_tag_manager", False)

    if _manage_tags_dialog is None and st.session_state.get("show_global_tag_manager"):
        with st.container(border=True):
            _manage_tags_modal(db)

    auto = json_tags(row.get("auto_tags"))
    if auto:
        with st.expander("Auto tags", expanded=False):
            badge_row(auto)

    notes = st.text_area(
        "Reviewer notes",
        row.get("review_notes") or "",
        height=180,
        placeholder="Briefly explain why the case is benign, unclear, suspicious, or a tool false positive.",
    )
    missing = st.text_area(
        "Missing evidence / follow-up",
        "",
        height=90,
        placeholder="Optional: what would make this case clearer?",
    )

    c1, c2 = st.columns([1, 1], gap="small")
    if c1.button("Save", type="primary", width="stretch"):
        _save_review(db, case_id, final, notes, selected_tags, all_tags)
        st.success("Review saved")
        st.rerun()
    if c2.button("Save & next", width="stretch"):
        _save_review(db, case_id, final, notes, selected_tags, all_tags)
        st.session_state["advance_after_save"] = True
        st.success("Review saved")
        st.rerun()

def _ensure_tag(db, case_id: int, tag_name: str) -> None:
    db.execute("INSERT OR IGNORE INTO tags(name, type) VALUES (?, 'manual')", (tag_name,))
    tag = db.one("SELECT id FROM tags WHERE name=?", (tag_name,))
    if tag:
        db.execute("INSERT OR IGNORE INTO case_tags(case_id, tag_id) VALUES (?, ?)", (case_id, tag["id"]))


def _save_review(db, case_id: int, final: str, notes: str, selected_tags: list[str], all_tags: list[dict]) -> None:
    db.execute("UPDATE cases SET final_label=?, review_notes=?, status='reviewed', updated_at=CURRENT_TIMESTAMP WHERE id=?", (final, notes, case_id))
    db.execute("DELETE FROM case_tags WHERE case_id=?", (case_id,))
    lookup = {t["name"]: t["id"] for t in all_tags}
    for name in selected_tags:
        tag_id = lookup.get(name)
        if tag_id:
            db.execute("INSERT OR IGNORE INTO case_tags(case_id, tag_id) VALUES (?, ?)", (case_id, tag_id))
