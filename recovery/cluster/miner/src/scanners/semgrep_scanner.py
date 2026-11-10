from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from src.scanners.codeql_scanner import _norm_path, added_line_numbers_by_file, finding_touches_added_lines
from src.utils.shell import parse_json_maybe, run_cmd


TEST_OR_EXAMPLE_PREFIXES = (
    "test/", "tests/", "testing/", "example/", "examples/", "doc/", "docs/", "notebook/", "notebooks/",
)


SEMGREP_SOURCE_EXTENSIONS = (
    ".py",
    ".pyi",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".vue",
)


def changed_semgrep_paths(files: list[dict[str, Any]]) -> list[str]:
    """Return changed source paths supported by the Semgrep pass."""
    paths: list[str] = []
    seen: set[str] = set()

    for f in files:
        name = _norm_path(f.get("filename"))

        if not name or name in seen:
            continue

        if name.lower().endswith(SEMGREP_SOURCE_EXTENSIONS):
            seen.add(name)
            paths.append(name)

    return paths


def changed_python_paths(files: list[dict[str, Any]]) -> list[str]:
    """Compatibility helper retained for existing tests and callers."""
    return [
        path
        for path in changed_semgrep_paths(files)
        if path.lower().endswith((".py", ".pyi"))
    ]


def _severity(extra: dict[str, Any]) -> str | None:
    sev = extra.get("severity") or extra.get("metadata", {}).get("impact")
    return str(sev).lower() if sev is not None else None


def _cwe(metadata: dict[str, Any]) -> str:
    cwe = metadata.get("cwe") or metadata.get("cwe_id") or metadata.get("cwe_ids") or []
    if isinstance(cwe, str):
        return cwe
    if isinstance(cwe, list):
        return ",".join(str(x) for x in cwe)
    return ""


def _metadata_list(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key) or []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def is_test_or_example_path(path: str) -> bool:
    """True for paths where SAST hits are usually test/example scaffolding noise."""
    p = _norm_path(path)
    name = Path(p).name
    if p.startswith(TEST_OR_EXAMPLE_PREFIXES):
        return True
    if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.py"):
        return True
    return False


def is_low_confidence_audit(finding: dict[str, Any]) -> bool:
    """True for broad Semgrep audit warnings that should not trigger CodeQL/review.

    These rules are useful notes, but the evidence export showed they create too much
    noise when used as candidate triggers, e.g. render_template_string in tests,
    pickle on local project metadata, and generic XML parser warnings.
    """
    confidence = str(finding.get("confidence") or "").lower()
    likelihood = str(finding.get("likelihood") or "").lower()
    subcategories = {str(x).lower() for x in finding.get("subcategory", [])}
    severity = str(finding.get("severity") or "").lower()
    if "audit" in subcategories and (confidence == "low" or likelihood == "low"):
        return True
    if severity == "warning" and confidence == "low":
        return True
    return False


def is_promotable_semgrep_finding(finding: dict[str, Any]) -> bool:
    """Whether a diff-linked Semgrep finding should become a SAST candidate.

    Non-promotable findings are not treated as maliciousness/downstream signals.
    They can still be examined in raw Semgrep output if needed, but they should not
    wake up CodeQL or mark the case as needs_review.
    """
    if is_test_or_example_path(str(finding.get("file") or "")):
        return False
    if is_low_confidence_audit(finding):
        return False
    return True


def parse_semgrep_json(data: dict[str, Any], repo_dir: Path | None = None) -> list[dict[str, Any]]:
    """Parse Semgrep JSON into the common scanner finding shape."""
    findings: list[dict[str, Any]] = []
    for res in data.get("results") or []:
        extra = res.get("extra") or {}
        metadata = extra.get("metadata") or {}
        path = str(res.get("path") or "")
        if repo_dir and path:
            try:
                path = str(Path(path).resolve().relative_to(repo_dir.resolve()))
            except Exception:
                pass
        start = res.get("start") or {}
        line = start.get("line")
        finding = {
            "file": _norm_path(path),
            "line": line,
            "rule": res.get("check_id"),
            "severity": _severity(extra),
            "cwe": _cwe(metadata),
            "description": extra.get("message") or res.get("check_id") or "Semgrep finding",
            "confidence": metadata.get("confidence"),
            "likelihood": metadata.get("likelihood"),
            "impact": metadata.get("impact"),
            "category": metadata.get("category"),
            "subcategory": _metadata_list(metadata, "subcategory"),
            "locations": [{"file": _norm_path(path), "line": line, "kind": "primary"}],
            "raw": res,
        }
        findings.append(finding)
    return findings



def semgrep_rejection_reasons(
    finding: dict[str, Any],
) -> list[str]:
    """Explain why a diff-linked Semgrep finding is not promoted."""
    reasons: list[str] = []

    if is_test_or_example_path(
        str(
            finding.get("file")
            or ""
        )
    ):
        reasons.append(
            "test_or_example_path"
        )

    if is_low_confidence_audit(
        finding
    ):
        reasons.append(
            "low_confidence_audit"
        )

    return reasons


def classify_semgrep_to_pr_delta(
    findings: list[dict[str, Any]],
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify every diff-linked Semgrep finding.

    Promoted findings remain downstream signals with introduced=1.
    Policy-filtered findings are retained as evidence with introduced=0.
    """
    added_lines = added_line_numbers_by_file(
        files
    )

    classified: list[
        dict[str, Any]
    ] = []

    for finding in findings:
        if not finding_touches_added_lines(
            finding,
            added_lines,
        ):
            continue

        enriched = dict(
            finding
        )

        rejection_reasons = (
            semgrep_rejection_reasons(
                enriched
            )
        )

        promoted = not rejection_reasons

        enriched["diff_linked"] = True
        enriched["promoted"] = promoted
        enriched[
            "rejection_reasons"
        ] = rejection_reasons

        enriched["introduced"] = (
            1
            if promoted
            else 0
        )

        enriched["finding_type"] = (
            "vulnerability"
            if promoted
            else "semgrep_filtered"
        )

        enriched["evidence"] = json.dumps(
            {
                "diff_linked": True,
                "promoted": promoted,
                "rejection_reasons": (
                    rejection_reasons
                ),
                "confidence": enriched.get(
                    "confidence"
                ),
                "likelihood": enriched.get(
                    "likelihood"
                ),
                "impact": enriched.get(
                    "impact"
                ),
                "category": enriched.get(
                    "category"
                ),
                "subcategory": enriched.get(
                    "subcategory"
                ),
            },
            sort_keys=True,
        )

        classified.append(
            enriched
        )

    return classified


def filter_semgrep_to_pr_delta(
    findings: list[dict[str, Any]],
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only promoted Semgrep findings touching added PR lines."""
    return [
        finding
        for finding in classify_semgrep_to_pr_delta(
            findings,
            files,
        )
        if bool(
            finding.get(
                "promoted"
            )
        )
    ]

def scan_head_with_semgrep(
    repo_url: str,
    head_sha: str,
    files: list[dict[str, Any]],
    *,
    semgrep_config: str = "p/security-audit",
    timeout_seconds: int = 300,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Run Semgrep on changed supported source files at PR head and return promoted findings.

    Semgrep is a fast established SAST triage layer. It does not prove maliciousness;
    it identifies source-code candidates that can be confirmed with CodeQL/manual review.
    Low-confidence audit hits and test/example-only hits are not promoted.
    """
    if not shutil.which("semgrep"):
        return [], {"status": "tool_missing", "stdout": "", "stderr": "semgrep executable not found on PATH"}
    paths = changed_semgrep_paths(files)
    if not paths:
        return [], {"status": "not_applicable", "stdout": "", "stderr": "No changed Semgrep-supported source files; Semgrep not applicable"}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        clone = run_cmd(["git", "clone", "--depth", "1", repo_url, "repo"], cwd=root, timeout=min(timeout_seconds, 300))
        if not clone.get("ok"):
            return [], {"status": "error", "stdout": clone.get("stdout", ""), "stderr": clone.get("stderr", "")}
        repo_dir = root / "repo"
        run_cmd(["git", "fetch", "--depth", "1", "origin", head_sha], cwd=repo_dir, timeout=min(timeout_seconds, 300))
        checkout = run_cmd(["git", "checkout", head_sha], cwd=repo_dir, timeout=min(timeout_seconds, 120))
        if not checkout.get("ok"):
            return [], {"status": "error", "stdout": checkout.get("stdout", ""), "stderr": checkout.get("stderr", "")}

        existing_paths = [p for p in paths if (repo_dir / p).exists()]
        if not existing_paths:
            return [], {"status": "not_applicable", "stdout": "", "stderr": "Changed source files are not present at head checkout"}

        out_json = root / "semgrep.json"
        cmd = [
            "semgrep",
            "--config",
            semgrep_config,
            "--json",
            "--metrics=off",
            "--quiet",
            "--output",
            str(out_json),
            *existing_paths,
        ]
        run = run_cmd(cmd, cwd=repo_dir, timeout=timeout_seconds)
        if run.get("returncode") == 124:
            return [], {"status": "timeout", "stdout": run.get("stdout", ""), "stderr": f"Semgrep timed out after {timeout_seconds} seconds"}
        if not out_json.exists():
            return [], {"status": "error", "stdout": run.get("stdout", ""), "stderr": run.get("stderr", "")}
        data = parse_json_maybe(out_json.read_text(encoding="utf-8", errors="ignore"))
        if not isinstance(data, dict):
            return [], {"status": "error", "stdout": run.get("stdout", ""), "stderr": "Semgrep did not produce valid JSON"}
        all_findings = parse_semgrep_json(
            data,
            repo_dir=repo_dir,
        )

        classified = classify_semgrep_to_pr_delta(
            all_findings,
            files,
        )

        promoted_count = sum(
            1
            for finding in classified
            if bool(
                finding.get(
                    "promoted"
                )
            )
        )

        filtered_count = (
            len(classified)
            - promoted_count
        )

        status = (
            "ok"
            if run.get("ok")
            else "ok_with_warnings"
        )

        stderr = run.get(
            "stderr",
            "",
        )

        stdout = (
            f"all_findings={len(all_findings)} "
            f"diff_linked={len(classified)} "
            f"promoted={promoted_count} "
            f"filtered={filtered_count}\n"
            + (
                run.get(
                    "stdout",
                    "",
                )
                or ""
            )
        )

        return classified, {
            "status": status,
            "stdout": stdout,
            "stderr": stderr,
        }
