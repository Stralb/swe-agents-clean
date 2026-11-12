from ui.retrieval import STREAM_BY_KEY, derive_query_terms, priority_score


def test_issue_steering_and_security_regression_streams_exist():
    assert "issue_steering" in STREAM_BY_KEY
    assert "security_regression" in STREAM_BY_KEY
    assert '"traceback"' in STREAM_BY_KEY["issue_steering"].terms
    assert '"CVE"' in STREAM_BY_KEY["security_regression"].terms


def test_new_stream_terms_are_derived_from_issue_text():
    row = {
        "issue_title": "CVE fix is too strict",
        "issue_body": "Steps to reproduce: this validation causes a false positive. Please rollback the security fix.",
        "pr_title": "compat fix",
        "pr_body": "Fixes #1",
        "link_methods": "body",
        "file_names": "src/auth.py",
        "ai_marker_terms": "",
    }
    terms = derive_query_terms(row)
    assert '"steps to reproduce"' in terms
    assert '"security fix"' in terms
    assert '"false positive"' in terms
    assert priority_score(row) >= 5
