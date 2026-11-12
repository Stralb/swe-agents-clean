from src.github.issue_linker import find_linked_issue_numbers


def test_same_repo_url_links():
    text = "Fixes https://github.com/freqtrade/freqtrade/issues/123"
    assert find_linked_issue_numbers(text, current_repo="freqtrade/freqtrade") == [(123, "closing-keyword")]


def test_third_party_changelog_url_does_not_link():
    text = "- `4181 <https://github.com/pytest-dev/pytest/issues/4181>`_: pytest changelog item"
    assert find_linked_issue_numbers(text, current_repo="freqtrade/freqtrade") == []


def test_bare_closing_keyword_links_current_repo_issue():
    assert find_linked_issue_numbers("Fixes #84", current_repo="Zie619/n8n-workflows") == [(84, "closing-keyword")]
