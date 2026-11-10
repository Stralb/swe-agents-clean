from src.pipeline.repo_universe import lookback_window, repo_window_pr_query
from src.github.client import GitHubClient


def test_repo_window_query_covers_full_lookback_and_excludes_maintenance_bots():
    window = lookback_window("2025-01-01", 12)
    assert window.start == "2025-01-01"
    assert window.end == "2026-01-01"
    q = repo_window_pr_query("owner/repo", window)
    assert "repo:owner/repo" in q
    assert "is:pr is:merged linked:issue" in q
    assert "merged:2025-01-01..2026-01-01" in q
    assert "-author:dependabot[bot]" in q
    assert "-author:renovate[bot]" in q


def test_github_client_pace_defaults_can_be_set_without_requesting():
    gh = GitHubClient(token=None, cache_enabled=False, search_min_interval_seconds=2.35, core_min_interval_seconds=0, jitter_seconds=0.65)
    assert gh.search_min_interval_seconds == 2.35
    assert gh.core_min_interval_seconds == 0
    assert gh.jitter_seconds == 0.65
from src.pipeline.repo_universe import global_active_pr_query


def test_global_active_pr_query_is_structural_and_not_keyword_bucket():
    window = lookback_window("2025-01-01", 12)
    q = global_active_pr_query(window, language="Python", min_stars=200)
    assert "is:pr is:merged linked:issue" in q
    assert "language:Python" in q
    assert "stars:>=200" in q
    assert "merged:2025-01-01..2026-01-01" in q
    for forbidden in ["bug", "traceback", "security", "dependency downgrade", "steps to reproduce"]:
        assert forbidden not in q.lower()
