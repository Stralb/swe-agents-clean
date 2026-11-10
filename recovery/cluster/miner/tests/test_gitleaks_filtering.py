from src.scanners.gitleaks_scanner import _is_baseline_file, _is_placeholder_evidence


def test_secret_baseline_files_are_known_false_positive_context():
    assert _is_baseline_file(".secrets.baseline")
    assert _is_baseline_file("subdir/.detect-secrets.baseline")


def test_placeholder_values_are_not_secret_evidence():
    assert _is_placeholder_evidence('data-token="REDACTED"')
    assert _is_placeholder_evidence("dummy_api_key")
    assert _is_placeholder_evidence("your_token_here")
