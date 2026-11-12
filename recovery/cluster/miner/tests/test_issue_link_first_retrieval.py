from __future__ import annotations

from src.pipeline.repo_universe import month_windows, repo_month_pr_query, shard_accept, star_band_queries
from ui.retrieval import BASE_QUERY, generated_queries


def test_repo_universe_star_band_queries_are_structural_not_keyword_buckets():
    qs = star_band_queries(language="Python", pushed_since="2024-01-01")
    assert len(qs) >= 5
    assert all("language:Python" in q for q in qs)
    assert all("archived:false" in q and "fork:false" in q for q in qs)
    assert all("bug" not in q and "traceback" not in q and "security" not in q for q in qs)


def test_repo_month_query_is_pr_first_structural_and_excludes_maintenance_bots():
    window = month_windows("2025-01-01", 1)[0]
    q = repo_month_pr_query("owner/repo", window)
    assert q.startswith("repo:owner/repo is:pr is:merged linked:issue draft:false")
    assert "merged:2025-01-01..2025-02-01" in q
    assert "-author:dependabot[bot]" in q
    assert "-author:renovate[bot]" in q
    assert "traceback" not in q and "requirements.txt" not in q and "CVE" not in q


def test_ui_generated_queries_match_downstream_first_strategy():
    qs = generated_queries('"requirements.txt"')
    assert qs == [BASE_QUERY]
    assert all('"requirements.txt"' not in q for q in qs)


def test_sharding_is_deterministic_and_partitioned():
    repos = ["a/r1", "b/r2", "c/r3", "d/r4", "e/r5"]
    shard0 = [r for r in repos if shard_accept(r, shard_count=2, shard_index=0)]
    shard1 = [r for r in repos if shard_accept(r, shard_count=2, shard_index=1)]
    assert sorted(shard0 + shard1) == sorted(repos)
    assert set(shard0).isdisjoint(shard1)
    assert shard0 == [r for r in repos if shard_accept(r, shard_count=2, shard_index=0)]
