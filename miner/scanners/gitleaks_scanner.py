from __future__ import annotations

from pathlib import Path, PurePosixPath
import shutil
import tempfile
from typing import Any

from miner.utils.shell import parse_json_maybe, run_cmd

PLACEHOLDER_VALUES = ("redacted", "example", "fake", "dummy", "placeholder", "changeme", "xxxxx", "xxxx", "your_token")
BASELINE_NAMES = {".secrets.baseline", ".detect-secrets.baseline"}


def _is_baseline_file(path: str | None) -> bool:
    name = PurePosixPath(path or "").name.lower()
    return name in BASELINE_NAMES


def _is_placeholder_evidence(text: str | None) -> bool:
    value = (text or "").lower()
    return any(token in value for token in PLACEHOLDER_VALUES)


def _safe_path(root: Path, filename: str) -> Path:
    # Keep original filename context for Gitleaks while preventing path traversal.
    safe_parts = [p for p in PurePosixPath(filename).parts if p not in {"", ".", ".."}]
    if not safe_parts:
        safe_parts = ["patch.txt"]
    return root.joinpath(*safe_parts)


def _added_lines_from_patch(patch: str) -> list[str]:
    out: list[str] = []
    for line in (patch or "").splitlines():
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+"):
            out.append(line[1:])
    return out


def scan_files_with_gitleaks(files: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Run the real Gitleaks CLI against added lines written to their real paths.

    Secret evidence must come from Gitleaks. No regex fallback exists. Known baseline
    metadata and placeholder/redacted values are not returned as secret findings.
    """
    if not shutil.which("gitleaks"):
        return [], {"stdout": "", "stderr": "gitleaks executable not found on PATH", "status": "tool_missing"}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        wrote = False
        source_lines_by_path: dict[str, list[str]] = {}

        for f in files:
            filename = f.get("filename") or "patch.txt"
            if _is_baseline_file(filename):
                continue
            added = _added_lines_from_patch(f.get("patch") or "")
            if not added:
                continue
            target = _safe_path(root, filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                "\n".join(added),
                encoding="utf-8",
            )

            relative_target = (
                target.relative_to(
                    root
                ).as_posix()
            )

            source_lines_by_path[
                relative_target
            ] = list(
                added
            )

            wrote = True
        if not wrote:
            return [], {"stdout": "", "stderr": "No added lines eligible for Gitleaks", "status": "not_applicable"}

        report = root / "gitleaks.json"
        result = run_cmd([
            "gitleaks", "detect",
            "--no-git",
            "--source", str(root),
            "--report-format", "json",
            "--report-path", str(report),
            "--redact",
        ], timeout=180)

        findings: list[dict[str, Any]] = []
        if report.exists():
            data = parse_json_maybe(report.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(data, list):
                for item in data:
                    file_path = (
                        item.get(
                            "File"
                        )
                        or ""
                    )

                    if str(
                        file_path
                    ).startswith(
                        str(
                            root
                        )
                    ):
                        rel = Path(
                            file_path
                        ).relative_to(
                            root
                        ).as_posix()

                    else:
                        rel = Path(
                            str(
                                file_path
                            )
                        ).as_posix()

                    start_line = item.get(
                        "StartLine"
                    )

                    source_evidence = ""

                    try:
                        line_index = (
                            int(
                                start_line
                            )
                            - 1
                        )

                    except (
                        TypeError,
                        ValueError,
                    ):
                        line_index = -1

                    source_lines = (
                        source_lines_by_path.get(
                            rel,
                            [],
                        )
                    )

                    if (
                        line_index >= 0
                        and line_index
                        < len(
                            source_lines
                        )
                    ):
                        source_evidence = (
                            source_lines[
                                line_index
                            ]
                        )

                    if _is_baseline_file(
                        rel
                    ):
                        continue

                    if (
                        source_evidence
                        and _is_placeholder_evidence(
                            source_evidence
                        )
                    ):
                        continue

                    report_evidence = (
                        item.get(
                            "Match"
                        )
                        or item.get(
                            "Secret"
                        )
                        or ""
                    )

                    if (
                        not report_evidence
                        or _is_placeholder_evidence(
                            report_evidence
                        )
                    ):
                        safe_evidence = (
                            "<redacted by gitleaks>"
                        )

                    else:
                        safe_evidence = (
                            report_evidence
                        )

                    findings.append(
                        {
                            "file": rel,
                            "line": start_line,
                            "rule": item.get(
                                "RuleID"
                            ),
                            "description": (
                                item.get(
                                    "Description"
                                )
                                or (
                                    "Potential secret "
                                    "introduced"
                                )
                            ),
                            "evidence": safe_evidence,
                            "raw": item,
                        }
                    )
        status = "ok" if result.get("ok") or report.exists() else "error"
        return findings, {"stdout": result.get("stdout", ""), "stderr": result.get("stderr", ""), "status": status}


def scan_patch_with_gitleaks(patch_text: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    # Backward-compatible wrapper for older tests; real pipeline uses scan_files_with_gitleaks.
    return scan_files_with_gitleaks([{"filename": "patch.diff", "patch": patch_text or ""}])
