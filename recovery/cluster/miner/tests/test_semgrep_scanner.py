from pathlib import Path

from src.scanners.semgrep_scanner import (
    changed_python_paths,
    filter_semgrep_to_pr_delta,
    parse_semgrep_json,
)


def test_semgrep_applicable_to_changed_python_anywhere():
    files = [
        {"filename": "README.md"},
        {"filename": "tests/test_demo.py"},
        {"filename": "scripts/tool.pyi"},
    ]
    assert changed_python_paths(files) == ["tests/test_demo.py", "scripts/tool.pyi"]


def test_semgrep_not_applicable_without_python_files():
    assert changed_python_paths([
        {"filename": "pyproject.toml"},
        {"filename": ".github/workflows/ci.yml"},
    ]) == []


def test_parse_semgrep_json_normalizes_findings():
    data = {
        "results": [
            {
                "check_id": "python.lang.security.audit.subprocess-shell-true",
                "path": "src/app.py",
                "start": {"line": 12, "col": 1},
                "extra": {
                    "message": "subprocess call with shell=True",
                    "severity": "WARNING",
                    "metadata": {"cwe": ["CWE-78"]},
                },
            }
        ]
    }
    findings = parse_semgrep_json(data)
    assert len(findings) == 1
    assert findings[0]["file"] == "src/app.py"
    assert findings[0]["line"] == 12
    assert findings[0]["rule"] == "python.lang.security.audit.subprocess-shell-true"
    assert findings[0]["cwe"] == "CWE-78"


def test_semgrep_findings_must_touch_added_lines():
    files = [{
        "filename": "src/app.py",
        "patch": "@@ -10,2 +10,3 @@\n context\n+dangerous()\n existing\n",
    }]
    findings = [
        {"file": "src/app.py", "line": 11, "rule": "hit", "description": "on diff"},
        {"file": "src/app.py", "line": 99, "rule": "old", "description": "not on diff"},
        {"file": "src/other.py", "line": 11, "rule": "other", "description": "other file"},
    ]
    promoted = filter_semgrep_to_pr_delta(findings, files)
    assert len(promoted) == 1
    assert promoted[0]["rule"] == "hit"
    assert promoted[0]["diff_linked"] is True


def test_semgrep_does_not_promote_test_file_findings_even_when_diff_linked():
    files = [{"filename": "tests/test_api.py", "patch": "@@ -1,1 +1,2 @@\n context\n+exec(dynamic_code)\n"}]
    findings = [{"file": "tests/test_api.py", "line": 2, "rule": "exec", "description": "exec", "severity": "warning"}]
    assert filter_semgrep_to_pr_delta(findings, files) == []


def test_semgrep_does_not_promote_low_confidence_audit_findings():
    files = [{"filename": "src/svg.py", "patch": "@@ -1,1 +1,2 @@\n context\n+import xml.etree.ElementTree as ET\n"}]
    findings = [{
        "file": "src/svg.py",
        "line": 2,
        "rule": "python.lang.security.use-defused-xml.use-defused-xml",
        "description": "use defusedxml",
        "severity": "error",
        "confidence": "LOW",
        "likelihood": "LOW",
        "subcategory": ["audit"],
    }]
    assert filter_semgrep_to_pr_delta(findings, files) == []


def test_semgrep_promotes_stronger_non_test_diff_linked_finding():
    files = [{"filename": "src/app.py", "patch": "@@ -1,1 +1,2 @@\n context\n+subprocess.run(cmd, shell=True)\n"}]
    findings = [{
        "file": "src/app.py",
        "line": 2,
        "rule": "python.lang.security.audit.subprocess-shell-true",
        "description": "shell true",
        "severity": "error",
        "confidence": "HIGH",
        "likelihood": "HIGH",
        "subcategory": ["security"],
    }]
    promoted = filter_semgrep_to_pr_delta(findings, files)
    assert len(promoted) == 1
    assert promoted[0]["promoted"] is True
