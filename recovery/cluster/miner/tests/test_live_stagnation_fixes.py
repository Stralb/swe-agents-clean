from pathlib import Path
from src.db.database import Database
from src.github.client import GitHubClient
from src.workers.job_queue import applicable_job_types, update_case_stages


def test_search_issues_accepts_start_page(monkeypatch):
    calls = []
    gh = GitHubClient(token=None, cache_enabled=False)

    def fake_paginate(path, params=None, max_pages=None, start_page=1):
        calls.append((path, params, max_pages, start_page))
        return iter([])

    monkeypatch.setattr(gh, "paginate", fake_paginate)
    list(gh.search_issues("q", per_page=25, max_pages=1, start_page=3))
    assert calls[0][3] == 3


def test_secret_job_applies_to_generic_valid_case():
    files = [{"filename": "config/runtime.json"}]
    assert "secret_ci" in applicable_job_types(files, include_codeql=False)


def test_no_jobs_case_does_not_become_clean(tmp_path):
    db_path = tmp_path / "miner.db"
    schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
    db = Database(db_path)
    db.init_schema(schema)
    db.execute("INSERT INTO repos(full_name, html_url, stars, language, archived) VALUES ('o/r','https://github.com/o/r',100,'Python',0)")
    db.execute("INSERT INTO issues(repo_id, github_id, number, url, title, body, author, state, labels, comments_count, created_at, updated_at, closed_at, word_count, is_english) VALUES (1,1,1,'u','i','','a','closed','[]',0,'2025-01-01','2025-01-01','2025-01-01',1,1)")
    db.execute("INSERT INTO pull_requests(repo_id, number, url, title, body, author, state, merged, merged_at, base_sha, head_sha, additions, deletions, changed_files_count) VALUES (1,2,'p','p','','a','closed',1,'2025-01-02','b','h',1,0,1)")
    db.execute("INSERT INTO cases(repo_id, issue_id, pr_id, status) VALUES (1,1,1,'metadata_collected')")
    update_case_stages(db)
    row = db.one("SELECT status FROM cases WHERE id=1")
    assert row["status"] == "scanner_running"


def test_paginate_max_pages_is_relative_to_start_page(monkeypatch):
    gh = GitHubClient(token=None, cache_enabled=False)
    seen_pages = []

    def fake_get(path, params=None):
        seen_pages.append(params["page"])
        return {"items": [{"id": params["page"]}] * params["per_page"]}

    monkeypatch.setattr(gh, "get", fake_get)
    items = list(gh.paginate("/search/issues", {"q": "x", "per_page": 2}, max_pages=2, start_page=5))
    assert seen_pages == [5, 6]
    assert len(items) == 4


def test_migration_repairs_retrieval_queries_stuck_on_page_one(tmp_path):
    db_path = tmp_path / "miner.db"
    schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
    db = Database(db_path)
    db.init_schema(schema)
    db.execute(
        """
        INSERT INTO retrieval_queries(stream_key, term, final_query, raw_count, next_page, exhausted, status)
        VALUES ('ci_cd_secrets', '"token"', 'q', 1000, 1, 0, 'ok')
        """
    )
    db.apply_migrations()
    row = db.one("SELECT next_page, exhausted, last_error FROM retrieval_queries WHERE final_query='q'")
    # Legacy rows with raw hits but no accounting are reset for replay so the
    # current accounting code can explain where every hit went.
    assert row["next_page"] == 1
    assert row["exhausted"] == 0
    assert "reset_legacy_unaccounted_retrieval_for_replay" in row["last_error"]

from src.pipeline.collect_pipeline import TARGETED_BASE_QUERY, _process_pr, _targeted_query_jobs, TARGETED_ISSUE_LINK_TERMS, TARGETED_STREAMS
from src.settings import RuntimeLimits, Settings


def test_targeted_base_query_constrains_search_to_title_body():
    assert "in:title,body" in TARGETED_BASE_QUERY


class FakeGitHubForProcess:
    def paginate(self, path, params=None, max_pages=None, start_page=1):
        if path.endswith("/pulls/2/files"):
            return iter([{"filename": "src/app.py", "patch": "+print(1)"}])
        if path.endswith("/issues/2/comments"):
            return iter([{"body": "This should close #1"}])
        if path.endswith("/pulls/2/commits"):
            return iter([])
        return iter([])

    def get(self, path):
        if path.endswith("/issues/1"):
            return {
                "id": 1,
                "number": 1,
                "html_url": "https://github.com/owner/repo/issues/1",
                "title": "Bug report",
                "body": "Steps to reproduce with enough words to pass the issue filter. " * 6,
                "user": {"login": "alice"},
                "state": "closed",
                "labels": [],
                "comments": 0,
                "created_at": "2025-02-01T00:00:00Z",
                "updated_at": "2025-02-02T00:00:00Z",
                "closed_at": "2025-02-03T00:00:00Z",
            }
        raise AssertionError(path)


def test_process_pr_uses_jan_2025_lookback_and_comment_link_fallback(tmp_path):
    db_path = tmp_path / "miner.db"
    schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
    db = Database(db_path)
    db.init_schema(schema)
    settings = Settings(
        config_path=Path("config.yml"),
        db_path=db_path,
        github_token=None,
        config={
            "github": {"include_merged_prs": True, "include_closed_unmerged_prs": False, "per_page": 50},
            "filters": {"min_issue_words": 10, "english_only": False, "exclude_bots": [], "exclude_non_behaviour_only": True},
            "collection": {"lookback_start": "2025-01-01", "lookback_months": 12, "fetch_pr_comments_for_issue_links": True},
            "ai_markers": {"high_confidence": [], "medium_confidence": []},
        },
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=None, max_cases_per_repo=10, max_seconds=None),
    )
    repo = {"full_name": "owner/repo", "html_url": "https://github.com/owner/repo", "stargazers_count": 100, "language": "Python", "archived": False}
    pr = {
        "id": 2,
        "number": 2,
        "html_url": "https://github.com/owner/repo/pull/2",
        "title": "Fix bug",
        "body": "No direct issue link here",
        "user": {"login": "bob"},
        "state": "closed",
        "merged": True,
        "merged_at": "2025-02-04T00:00:00Z",
        "head": {"ref": "bugfix", "sha": "h"},
        "base": {"ref": "main", "sha": "b"},
    }
    count, repo_count = _process_pr(db=db, gh=FakeGitHubForProcess(), settings=settings, repo=repo, pr=pr, start=0, case_count=0)
    assert count == 1
    assert repo_count == 1
    assert db.one("SELECT COUNT(*) AS n FROM cases")["n"] == 1


def test_migration_backfills_missing_scanner_jobs(tmp_path):
    db_path = tmp_path / "miner.db"
    schema = Path(__file__).resolve().parents[1] / "src" / "db" / "schema.sql"
    db = Database(db_path)
    db.init_schema(schema)
    db.execute("INSERT INTO repos(full_name, html_url, stars, language, archived) VALUES ('o/r','https://github.com/o/r',100,'Python',0)")
    db.execute("INSERT INTO issues(repo_id, github_id, number, url, title, body, author, state, labels, comments_count, created_at, updated_at, closed_at, word_count, is_english) VALUES (1,1,1,'u','i','','a','closed','[]',0,'2025-01-01','2025-01-01','2025-01-01',1,1)")
    db.execute("INSERT INTO pull_requests(repo_id, number, url, title, body, author, state, merged, merged_at, base_sha, head_sha, additions, deletions, changed_files_count) VALUES (1,2,'p','p','','a','closed',1,'2025-01-02','b','h',1,0,1)")
    db.execute("INSERT INTO cases(repo_id, issue_id, pr_id, status) VALUES (1,1,1,'scanner_running')")
    db.execute("INSERT INTO scanner_jobs(case_id, job_type, status) VALUES (1, 'source_code', 'ok')")
    db.apply_migrations()
    rows = db.query("SELECT job_type FROM scanner_jobs WHERE case_id=1 ORDER BY job_type")
    assert [r["job_type"] for r in rows] == ["codeql", "dependency_downgrade", "osv_dependency", "secret_ci"]


def test_next_iteration_query_plan_is_wide_first_and_high_precision():
    settings = Settings(
        config_path=Path("config.yml"),
        db_path=Path("miner.db"),
        github_token=None,
        config={
            "github": {"min_stars": 200, "language": "Python"},
            "collection": {
                "lookback_start": "2025-01-01",
                "query_phases": ["single_stream", "combined_issue_link_stream", "issue_link_baseline"],
            },
        },
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=None, max_cases_per_repo=3, max_seconds=None),
    )
    jobs = _targeted_query_jobs(settings)
    assert all(j[0] != "issue_links" for j in jobs[:6])
    assert all('stars:>=200' in q and 'merged:>=2025-01-01' in q for _, _, q in jobs[:20])
    assert not any('"fix #"' in q for _, _, q in jobs)
    # The first phase is single-stream and round-robin across streams.
    first_stream_phase = jobs[:6]
    assert len({stream for stream, _, _ in first_stream_phase}) == 6
    assert not any('"fixes #"' in q or '"closes #"' in q or '"resolves #"' in q for _, _, q in first_stream_phase)


def test_default_terms_exclude_noisy_broad_terms():
    all_terms = {term for _, terms in TARGETED_STREAMS for term in terms}
    for noisy in {'"auth"', '"token"', '"CI"', '"env"', '"workflow"', '"dependency"', '"dependencies"', '"validation"', '"edge case"', '"test case"'}:
        assert noisy not in all_terms
    assert TARGETED_ISSUE_LINK_TERMS == ('"fixes #"', '"closes #"', '"resolves #"')
