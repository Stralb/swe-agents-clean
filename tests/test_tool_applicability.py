import pytest

from src.filters.tool_applicability import (
    has_any_applicable_downstream_worker,
    has_primary_applicable_downstream_worker,
    is_dependency_file,
    is_python_file,
    route_reasons,
)


def test_python_source_routes_to_codeql():
    files = [{"filename": "src/app.py", "patch": "+print('x')"}]
    routes = route_reasons(files)
    assert is_python_file("src/app.py")
    assert routes["codeql"].startswith("artifact_regions=source/agent/script languages=python")
    assert routes["osv_dependency"] == "not_applicable:no_dependency_config_region"
    assert routes["trivy_dependency"] == "not_applicable:no_dependency_config_region"
    assert routes["dependency_downgrade"] == "not_applicable:no_dependency_config_region"
    assert routes["secret_ci"].startswith("artifact_regions=ci/secret/unknown/patch")
    assert has_primary_applicable_downstream_worker(files)


def test_dependency_artifacts_route_to_dependency_scanners():
    assert is_dependency_file("requirements/base.txt")
    assert is_dependency_file("pyproject.toml")
    files = [{"filename": "requirements/base.txt", "patch": "-idna==3.10\n+idna==3.9"}]
    routes = route_reasons(files)
    assert routes["codeql"] == "not_applicable:no_source_code_region"
    for name in ("osv_dependency", "trivy_dependency", "dependency_downgrade"):
        assert routes[name].startswith("artifact_region=dependency_config paths=")
    assert routes["secret_ci"].startswith("artifact_regions=ci/secret/unknown/patch")


def test_patchless_document_has_no_scanner_routes():
    routes = route_reasons([{"filename": "docs/readme.md", "patch": ""}])
    for name in ("codeql", "osv_dependency", "trivy_dependency", "dependency_downgrade", "secret_ci"):
        assert routes[name].startswith("not_applicable:")
    assert routes["artifact_profile"] == "regions=non_behavioral:1"


def test_ci_workflow_is_classified_and_routed_to_secret_scan():
    files = [{"filename": ".github/workflows/test.yml", "patch": "+env:\n+  TOKEN: ${{ secrets.X }}"}]
    routes = route_reasons(files)
    assert routes["artifact_profile"] == "regions=ci_workflow:1"
    assert routes["secret_ci"].startswith("artifact_regions=ci/secret/unknown/patch")
    assert has_any_applicable_downstream_worker(files)


def test_dependency_downgrade_finding_reports_line_number():
    from src.scanners.dependency_diff import detect_dependency_regressions

    files = [{
        "filename": "requirements.txt",
        "patch": "@@ -8,2 +8,2 @@\n-idna==3.10\n+idna==3.9\n",
    }]
    findings = detect_dependency_regressions(files)
    assert findings
    assert findings[0]["change_type"] == "dependency_downgrade"
    assert findings[0]["line"] == 8


def test_javascript_typescript_source_routes_to_codeql():
    files = [{"filename": "frontend/App.tsx", "patch": "+const x = 1"}]
    routes = route_reasons(files)
    assert "javascript-typescript" in routes["codeql"]
    assert has_primary_applicable_downstream_worker(files)


@pytest.mark.xfail(
    strict=True,
    reason="Historical has_any helper mistakes artifact_profile metadata for an applicable worker",
)
def test_patchless_docs_should_have_no_applicable_worker():
    assert not has_any_applicable_downstream_worker([{"filename": "docs/readme.md", "patch": ""}])


@pytest.mark.xfail(
    strict=True,
    reason="Historical has_primary helper treats an absent ci_security route as applicable",
)
def test_docs_only_patch_should_not_have_primary_worker():
    assert not has_primary_applicable_downstream_worker([{"filename": "README.md", "patch": "+hello"}])
