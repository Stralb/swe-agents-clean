from pathlib import Path

import yaml

from src.pipeline.collect_pipeline import _targeted_query_jobs, TARGETED_ISSUE_LINK_TERMS
from src.settings import RuntimeLimits, Settings


def _settings(config):
    return Settings(
        config_path=Path('config.yml'),
        db_path=Path('data/test.db'),
        github_token='token',
        config=config,
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=10, max_cases_per_repo=3, max_seconds=None),
    )


def test_wide_first_defaults_are_not_early_drop_caps():
    cfg = yaml.safe_load(Path('config.yml').read_text())
    assert cfg['github']['min_stars'] == 200
    assert cfg['github']['strict_primary_language'] is False
    assert cfg['collection']['max_raw_hits_per_repo_per_pass'] == 0
    assert cfg['collection']['max_processed_prs_per_repo'] >= 50
    assert cfg['collection']['max_prs_per_repo_per_query'] == 1
    assert cfg['collection']['max_new_prs_per_repo_per_run'] == 2
    assert cfg['collection']['repo_walk_enabled'] is False


def test_query_phases_prioritize_issue_linked_work_before_single_stream():
    cfg = yaml.safe_load(Path('config.yml').read_text())
    jobs = _targeted_query_jobs(_settings(cfg))
    assert jobs
    first_issue_baseline = next(i for i, (stream, _, _) in enumerate(jobs) if stream == 'issue_links')
    first_combined = next(i for i, (stream, _, q) in enumerate(jobs) if stream != 'issue_links' and any(t in q for t in TARGETED_ISSUE_LINK_TERMS))
    first_single = next((i for i, (stream, _, q) in enumerate(jobs) if stream != 'issue_links' and not any(t in q for t in TARGETED_ISSUE_LINK_TERMS)), None)
    assert first_issue_baseline == 0
    assert first_combined > first_issue_baseline
    assert first_single is None or first_single > first_combined
    assert '"fix #"' not in ' '.join(q for _, _, q in jobs)


def test_targeted_base_uses_2025_and_200_stars():
    cfg = yaml.safe_load(Path('config.yml').read_text())
    q = _targeted_query_jobs(_settings(cfg))[0][2]
    assert 'stars:>=200' in q
    assert 'merged:>=2025-01-01' in q
    assert 'in:title,body' in q
