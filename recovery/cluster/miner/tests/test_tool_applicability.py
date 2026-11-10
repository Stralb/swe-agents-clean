from src.filters.tool_applicability import (
    has_any_applicable_downstream_worker,
    has_primary_applicable_downstream_worker,
    is_dependency_file,
    is_python_file,
    route_reasons,
)


def test_python_files_route_to_codeql_without_dependency_workers():
    routes = route_reasons([{"filename": "src/app.py", "patch": "+print('x')"}])
    assert is_python_file("src/app.py")
    assert routes["codeql"].startswith("changed CodeQL-supported source files (python)")
    assert routes["osv_dependency"] == "not_applicable:no_dependency_files_changed"
    assert routes["dependency_downgrade"] == "not_applicable:no_dependency_files_changed"
    assert routes["secret_ci"].startswith("patch contains added lines")


def test_dependency_files_route_to_osv_and_downgrade_workers():
    assert is_dependency_file("requirements/base.txt")
    assert is_dependency_file("pyproject.toml")
    routes = route_reasons([{"filename": "requirements/base.txt", "patch": "-idna==3.10\n+idna==3.9"}])
    assert routes["codeql"] == "not_applicable:no_codeql_supported_source_files_changed"
    assert routes["osv_dependency"].startswith("changed dependency manifest/lock files")
    assert routes["dependency_downgrade"].startswith("changed dependency manifest/lock files")
    assert routes["secret_ci"].startswith("patch contains added lines")


def test_patchless_docs_are_not_tool_applicable():
    files = [{"filename": "docs/readme.md", "patch": ""}]
    routes = route_reasons(files)
    assert routes == {
        "codeql": "not_applicable:no_codeql_supported_source_files_changed",
        "osv_dependency": "not_applicable:no_dependency_files_changed",
        "dependency_downgrade": "not_applicable:no_dependency_files_changed",
        "ci_security": "not_applicable:no_ci_or_workflow_security_files_changed",
        "secret_ci": "not_applicable:no_added_patch_lines",
    }
    assert not has_any_applicable_downstream_worker(files)
    assert not has_primary_applicable_downstream_worker(files)


def test_non_python_patch_is_secret_scan_applicable():
    files = [{"filename": ".github/workflows/test.yml", "patch": "+env:\n+  TOKEN: ${{ secrets.X }}"}]
    routes = route_reasons(files)
    assert routes["ci_security"].startswith("changed CI/workflow/security config files")
    assert routes["secret_ci"].startswith("patch contains added lines")
    assert has_any_applicable_downstream_worker(files)
    assert has_primary_applicable_downstream_worker(files)


def test_dependency_downgrade_findings_include_added_line_numbers():
    from src.scanners.dependency_diff import detect_dependency_regressions
    files = [{
        "filename": "requirements.txt",
        "patch": "@@ -8,2 +8,2 @@\n-idna==3.10\n+idna==3.9\n",
    }]
    findings = detect_dependency_regressions(files)
    assert findings
    assert findings[0]["change_type"] == "dependency_downgrade"
    assert findings[0]["line"] == 8


def test_javascript_typescript_source_routes_to_codeql_primary():
    files = [{"filename": "frontend/App.tsx", "patch": "+const x = 1"}]
    routes = route_reasons(files)
    assert "javascript-typescript" in routes["codeql"]
    assert has_primary_applicable_downstream_worker(files)


def test_secret_only_patch_does_not_qualify_primary_worker():
    files = [{"filename": "README.md", "patch": "+hello"}]
    assert has_any_applicable_downstream_worker(files)
    assert not has_primary_applicable_downstream_worker(files)
