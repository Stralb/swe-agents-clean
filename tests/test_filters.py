from miner.filters.pr_filters import categorize_file


def test_categorize_source():
    assert categorize_file("src/app.py") == "source"
    assert categorize_file("requirements.txt") == "dependency"
