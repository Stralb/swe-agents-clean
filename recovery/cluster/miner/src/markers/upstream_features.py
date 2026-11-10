from __future__ import annotations

import json
import re

CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
INLINE_CODE_RE = re.compile(r"`[^`\n]{2,120}`")
TRACEBACK_RE = re.compile(r"(traceback|stack trace|exception|error:|warning:|\s+at\s+\w+\(|file \".*\", line \d+)", re.I)
FILE_PATH_RE = re.compile(r"(?:[\w.-]+/)+[\w.-]+\.(?:py|js|ts|java|go|rs|c|cpp|h|yml|yaml|toml|json|txt)", re.I)
FUNC_RE = re.compile(r"\b(?:[a-zA-Z_]\w*)\s*\(|\b[A-Z][A-Za-z0-9_]+(?:Error|Exception|Config|Parser|Client|Handler)\b")
DEP_RE = re.compile(r"\b(?:requirements\.txt|pyproject\.toml|setup\.py|pipfile|poetry|uv\.lock|pdm\.lock|pip|version|dependency|CVE-\d{4}-\d+)\b", re.I)
FIX_RE = re.compile(r"\b(?:fix by|should use|use this|change .* to|remove|revert|disable|relax|replace .* with|suggested fix)\b", re.I)

REPRO_RE = re.compile(r"\b(steps to reproduce|minimal repro|reproducer|reproduction|mre)\b", re.I)
EXPECTED_RE = re.compile(r"\b(expected (behavior|behaviour|result)|actual (behavior|behaviour|result))\b", re.I)
FAILING_TEST_RE = re.compile(r"\b(failing test|test fails|pytest|regression test)\b", re.I)
SECURITY_RE = re.compile(r"\b(CVE-\d{4}-\d+|security regression|security fix|bypass|disable check|too strict|false positive|sanitize|validation)\b", re.I)
CI_RE = re.compile(r"\b(pull_request_target|GITHUB_TOKEN|secrets\.|permissions:|id-token|workflow_dispatch|actions/github-script|printenv)\b", re.I)
AI_RE = re.compile(r"\b(Claude Code|Codex|Copilot|Devin|Cursor|OpenHands|Aider|AI-generated|agent-generated|LLM-generated)\b", re.I)


def _count(pattern: re.Pattern[str], text: str) -> int:
    return len(pattern.findall(text))


def extract_upstream_features(title: str | None, body: str | None) -> dict:
    issue_body = body or ""
    text = f"{title or ''}\n{issue_body}"
    code_blocks = CODE_BLOCK_RE.findall(text)
    code_block_chars = sum(len(block) for block in code_blocks)
    largest_code_block_chars = max((len(block) for block in code_blocks), default=0)
    body_chars = len(issue_body.strip())
    body_words = len(re.findall(r"\b\w+\b", issue_body))
    code_block_ratio = (code_block_chars / max(1, len(text))) if text else 0.0
    features = {
        "issue_body_chars": body_chars,
        "issue_body_words": body_words,
        "issue_total_chars": len(text),
        "code_block_chars": code_block_chars,
        "largest_code_block_chars": largest_code_block_chars,
        "code_block_ratio": round(code_block_ratio, 4),
        "high_context_load": body_chars >= 3000,
        "code_heavy_issue": code_block_ratio >= 0.35,
        "large_code_block": largest_code_block_chars >= 1000,
        "has_code_block": bool(CODE_BLOCK_RE.search(text)),
        "has_inline_code": bool(INLINE_CODE_RE.search(text)),
        "has_traceback_or_log": bool(TRACEBACK_RE.search(text)),
        "has_file_path": bool(FILE_PATH_RE.search(text)),
        "has_function_or_class": bool(FUNC_RE.search(text)),
        "has_dependency_or_version": bool(DEP_RE.search(text)),
        "has_suggested_fix": bool(FIX_RE.search(text)),
        # Rich upstream indicators stored in feature_json only; they are never
        # used as candidate-inclusion filters in the downstream-first pipeline.
        "has_reproduction_steps": bool(REPRO_RE.search(text)),
        "has_expected_actual": bool(EXPECTED_RE.search(text)),
        "has_failing_test_signal": bool(FAILING_TEST_RE.search(text)),
        "has_security_steering_signal": bool(SECURITY_RE.search(text)),
        "has_ci_or_secret_steering_signal": bool(CI_RE.search(text)),
        "has_ai_text_signal": bool(AI_RE.search(text)),
        "code_block_count": _count(CODE_BLOCK_RE, text),
        "inline_code_count": _count(INLINE_CODE_RE, text),
        "file_path_count": _count(FILE_PATH_RE, text),
    }
    features["feature_json"] = json.dumps({k: v for k, v in features.items() if k != "feature_json"})
    return features
