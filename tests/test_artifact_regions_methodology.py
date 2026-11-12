from miner.artifacts.regions import classify_file, classify_files, profile_summary
from miner.filters.tool_applicability import route_reasons


def test_dependency_config_routes_dependency_scanners_not_issue_keywords():
    routes = route_reasons([{"filename": "pyproject.toml", "patch": "+requests==2.0\n"}])
    assert routes["dependency_downgrade"].startswith("artifact_region=dependency_config")
    assert routes["osv_dependency"].startswith("artifact_region=dependency_config")
    assert routes["codeql"].startswith("not_applicable:")


def test_ci_workflow_and_unknown_machine_readable_are_retained_for_broad_scan():
    files = [
        {"filename": ".github/workflows/ci.yml", "patch": "+permissions: write-all\n"},
        {"filename": "config/custom.policy", "patch": "+allow=*\n"},
    ]
    classes = classify_files(files)
    assert [c.region for c in classes] == ["ci_workflow", "unknown_machine_readable"]
    routes = route_reasons(files)
    assert routes["secret_ci"].startswith("artifact_regions=")


def test_generated_vendor_is_not_silently_dropped():
    c = classify_file("vendor/generated/client.pb.go")
    assert c.region == "generated_vendor"
    assert c.scanner_routes == ["low_priority_sample"]
    assert c.confidence == "medium"


def test_agentic_tooling_is_explicit_region():
    c = classify_file("src/mcp/tools/runner.py")
    assert c.region == "agentic_tooling"
    assert "agentic_tooling" in c.scanner_routes


def test_profile_summary_counts_region_yield_inputs():
    summary = profile_summary(classify_files(["src/server.py", "go.mod", "README.md"]))
    assert summary["region_counts"] == {
        "source_code": 1,
        "dependency_config": 1,
        "non_behavioral": 1,
    }
    assert summary["file_count"] == 3
