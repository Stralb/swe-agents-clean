from src.scanners.codeql_scanner import (
    added_line_numbers_by_file,
    diff_findings,
    filter_findings_to_pr_delta,
    finding_touches_added_lines,
    has_python_source_changes,
)


def test_codeql_applicable_when_any_python_file_changed():
    assert has_python_source_changes([{"filename": "src/app.py"}])
    assert has_python_source_changes([{"filename": "tests/test_app.py"}])
    assert has_python_source_changes([{"filename": "pkg/types.pyi"}])


def test_codeql_not_applicable_for_non_python_changes():
    assert not has_python_source_changes([{"filename": ".github/workflows/ci.yml"}])
    assert not has_python_source_changes([{"filename": "pyproject.toml"}])
    assert not has_python_source_changes([{"filename": "README.md"}])


def test_added_line_numbers_are_extracted_from_unified_diff():
    files = [{
        "filename": "src/app.py",
        "patch": "@@ -10,3 +10,5 @@\n context\n-old\n+new_one\n+new_two\n context2\n",
    }]
    assert added_line_numbers_by_file(files) == {"src/app.py": {11, 12}}


def test_codeql_finding_must_touch_added_line_to_promote():
    added = {"src/app.py": {11, 12}}
    finding = {"file": "src/app.py", "line": 11, "rule": "py/test", "description": "demo"}
    unrelated = {"file": "src/app.py", "line": 20, "rule": "py/test", "description": "demo"}
    other_file = {"file": "src/other.py", "line": 11, "rule": "py/test", "description": "demo"}
    assert finding_touches_added_lines(finding, added)
    assert not finding_touches_added_lines(unrelated, added)
    assert not finding_touches_added_lines(other_file, added)


def test_related_codeflow_location_can_link_finding_to_diff():
    added = {"src/app.py": {42}}
    finding = {
        "file": "src/sink.py",
        "line": 10,
        "rule": "py/test",
        "description": "demo",
        "locations": [
            {"file": "src/sink.py", "line": 10, "kind": "primary"},
            {"file": "src/app.py", "line": 42, "kind": "codeflow"},
        ],
    }
    assert finding_touches_added_lines(finding, added)


def test_project_wide_codeql_alerts_are_not_promoted_without_diff_link():
    files = [{
        "filename": "src/changed.py",
        "patch": "@@ -1,1 +1,2 @@\n old\n+new\n",
    }]
    base = []
    head = [
        {"file": "src/unrelated.py", "line": 99, "rule": "py/log-injection", "description": "Log injection"},
        {"file": "src/changed.py", "line": 2, "rule": "py/path-injection", "description": "Path injection"},
    ]
    introduced = diff_findings(base, head)
    promoted = filter_findings_to_pr_delta(introduced, files)
    assert len(promoted) == 1
    assert promoted[0]["file"] == "src/changed.py"
    assert promoted[0]["diff_linked"] is True


def test_existing_alert_line_shift_key_does_not_count_as_new_by_line_only():
    base = [{"file": "src/app.py", "line": 10, "rule": "py/log-injection", "description": "Log injection"}]
    head = [{"file": "src/app.py", "line": 12, "rule": "py/log-injection", "description": "Log injection"}]
    assert diff_findings(base, head) == []
