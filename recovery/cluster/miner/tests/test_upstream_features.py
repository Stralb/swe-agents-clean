from src.markers.upstream_features import extract_upstream_features


def test_features_code_block():
    f = extract_upstream_features("Bug", "```python\nprint(1)\n```\nTraceback error")
    assert f["has_code_block"]
    assert f["has_traceback_or_log"]


def test_context_load_features_are_recorded_not_used_as_filters():
    body = "A" * 3100 + "\n```python\n" + "print(1)\n" * 200 + "```"
    f = extract_upstream_features("Huge repro", body)
    assert f["issue_body_chars"] >= 3100
    assert f["high_context_load"] is True
    assert f["code_block_chars"] > 1000
    assert f["large_code_block"] is True
