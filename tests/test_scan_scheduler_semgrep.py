from src.pipeline.scan_pipeline import _enabled_cheap, _codeql_trigger_condition


def test_cheap_scanners_are_approved_downstream_workers_by_default():
    assert _enabled_cheap({"gitleaks": True, "osv": True, "dependency_downgrade": True, "semgrep": True}) == [
        "gitleaks",
        "dependency-diff",
        "osv-scanner",
    ]


def test_semgrep_positive_trigger_is_ignored_in_downstream_first_pipeline():
    assert _codeql_trigger_condition({"codeql_trigger": "semgrep_positive"}) == ""


def test_codeql_all_python_trigger_does_not_require_semgrep():
    assert _codeql_trigger_condition({"codeql_trigger": "all_python"}) == ""
