import json
from pathlib import Path

import pytest

from src.github.client import GitHubAPIError, GitHubClient, GitHubSecondaryRateLimit
from src.pipeline.collect_pipeline import _process_pr
from src.settings import RuntimeLimits, Settings


class DummyResponse:
    def __init__(self, status_code: int, text: str, headers=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}


class FakeDB:
    def __init__(self):
        self.exclusions = []

    def log_excluded_case(self, repo, issue_number, pr_number, reason, details="", changed_files=None):
        self.exclusions.append((repo, issue_number, pr_number, reason, details, changed_files))


class FilesUnavailableGH:
    def paginate(self, path, params=None, max_pages=None):
        raise GitHubAPIError("https://api.github.com" + path, 422, "Server Error: Sorry, this diff is taking too long to generate")


def make_settings():
    return Settings(
        config_path=Path("config.yml"),
        db_path=Path("data/test.db"),
        github_token="token",
        config={
            "github": {"include_merged_prs": True, "include_closed_unmerged_prs": False, "per_page": 50},
            "filters": {"min_issue_words": 1, "english_only": False, "exclude_bots": [], "exclude_non_behaviour_only": True},
            "collection": {"lookback_months": 12, "log_excluded_cases": True},
        },
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=10, max_cases_per_repo=10, max_seconds=None),
    )


def test_github_422_diff_not_available_is_transient():
    gh = GitHubClient(cache_enabled=False)
    resp = DummyResponse(422, '{"message":"Server Error: Sorry, this diff is taking too long to generate","errors":[{"field":"diff","code":"not_available"}]}')
    assert gh._is_transient_github_failure(resp)


def test_process_pr_logs_and_skips_when_pr_files_unavailable():
    db = FakeDB()
    settings = make_settings()
    repo = {"full_name": "owner/repo"}
    pr = {
        "number": 19,
        "merged_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z",
        "user": {"login": "human"},
        "title": "Fixes #1",
        "body": "Fixes #1",
        "head": {"ref": "fix-1"},
    }

    case_count, repo_case_count = _process_pr(
        db=db,
        gh=FilesUnavailableGH(),
        settings=settings,
        repo=repo,
        pr=pr,
        start=0,
        case_count=0,
        repo_case_count=0,
    )

    assert case_count == 0
    assert repo_case_count == 0
    assert db.exclusions
    assert db.exclusions[0][3] == "pr_files_unavailable"

class SequencedGetGH(GitHubClient):
    def __init__(self):
        pass

    def get(self, path, params=None):
        page = (params or {}).get("page")
        if page == 1:
            return {"items": [{"full_name": "owner/repo"}] * 2}
        raise GitHubAPIError("https://api.github.com/search/repositories", 422, '{"message":"Only the first 1000 search results are available"}')


def test_paginate_treats_github_search_1000_boundary_as_stop_not_failure():
    gh = SequencedGetGH()
    items = list(gh.paginate("/search/repositories", {"q": "language:Python", "per_page": 2}))
    assert len(items) == 2


def test_search_repos_caps_pages_to_github_1000_window(monkeypatch):
    seen = {}

    def fake_paginate(self, path, params=None, max_pages=None):
        seen["path"] = path
        seen["params"] = params
        seen["max_pages"] = max_pages
        return iter([])

    monkeypatch.setattr(GitHubClient, "paginate", fake_paginate)
    gh = GitHubClient(cache_enabled=False)
    list(gh.search_repos("language:Python", per_page=100))
    assert seen["path"] == "/search/repositories"
    assert seen["params"]["per_page"] == 100
    assert seen["max_pages"] == 10


def test_secondary_limit_stops_immediately_and_publishes_shared_cooldown(tmp_path, monkeypatch):
    cooldown = tmp_path / "github-secondary.json"
    gh = GitHubClient(
        cache_enabled=False,
        cache_dir=tmp_path / "cache-a",
        secondary_cooldown_path=cooldown,
        secondary_cooldown_base_seconds=300,
        secondary_cooldown_max_seconds=300,
        max_secondary_retries=9,
    )
    calls = []

    def limited_get(*args, **kwargs):
        calls.append(args[0])
        return DummyResponse(
            403,
            '{"message":"You have exceeded a secondary rate limit. Please wait a few minutes."}',
            {
                "X-RateLimit-Remaining": "27",
                "X-RateLimit-Limit": "30",
                "X-GitHub-Request-Id": "TEST:SECONDARY",
            },
        )

    monkeypatch.setattr(gh.session, "get", limited_get)
    with pytest.raises(GitHubSecondaryRateLimit):
        gh.get("/search/issues", {"q": "repo:owner/repo is:pr"})

    assert len(calls) == 1
    payload = json.loads(cooldown.read_text(encoding="utf-8"))
    assert payload["wait_seconds"] == 300
    assert payload["request_id"] == "TEST:SECONDARY"

    blocked = GitHubClient(
        cache_enabled=False,
        cache_dir=tmp_path / "cache-b",
        secondary_cooldown_path=cooldown,
    )

    def should_not_call(*args, **kwargs):
        raise AssertionError("active shared cooldown must prevent the HTTP call")

    monkeypatch.setattr(blocked.session, "get", should_not_call)
    with pytest.raises(GitHubSecondaryRateLimit, match="global secondary-rate cooldown"):
        blocked.get("/repos/owner/repo/pulls")


def test_closed_pulls_uses_core_repository_endpoint(monkeypatch, tmp_path):
    seen = {}
    gh = GitHubClient(cache_enabled=False, cache_dir=tmp_path / "cache")

    def fake_paginate(path, params=None, max_pages=None, start_page=1):
        seen.update(path=path, params=params, max_pages=max_pages)
        return iter([{"number": 7, "merged_at": "2026-01-01T00:00:00Z"}])

    monkeypatch.setattr(gh, "paginate", fake_paginate)
    pulls = list(gh.closed_pulls("owner/repo", per_page=100, max_pages=2))

    assert pulls[0]["number"] == 7
    assert seen["path"] == "/repos/owner/repo/pulls"
    assert seen["params"]["state"] == "closed"
    assert seen["max_pages"] == 2


def test_placeholder_for_resilience_suite_keeps_pytest_collecting():
    assert True

class IssueTooShortDB(FakeDB):
    def insert_or_get_repo(self, repo):
        return 1

    def upsert_pr(self, repo_id, pr):
        return 2

    def replace_pr_files(self, pr_id, files):
        self.files = files


class IssueTooShortGH:
    def paginate(self, path, params=None, max_pages=None):
        if path.endswith("/pulls/7/files"):
            return iter([{"filename": "src/app.py", "patch": "@@\n+print(1)"}])
        return iter([])

    def get(self, path, params=None):
        if path.endswith("/issues/1"):
            return {
                "number": 1,
                "title": "Tiny issue",
                "body": "too short",
                "created_at": "2026-06-01T00:00:00Z",
                "closed_at": "2026-06-02T00:00:00Z",
                "updated_at": "2026-06-02T00:00:00Z",
                "labels": [],
            }
        raise AssertionError(path)


def test_process_pr_excludes_issue_body_too_short():
    db = IssueTooShortDB()
    settings = Settings(
        config_path=Path("config.yml"),
        db_path=Path("data/test.db"),
        github_token="token",
        config={
            "github": {"include_merged_prs": True, "include_closed_unmerged_prs": False, "per_page": 50},
            "filters": {"issue_min_body_chars": 200, "exclude_bots": [], "exclude_non_behaviour_only": True, "exclude_docs_scope_only": True},
            "collection": {"lookback_months": 12, "log_excluded_cases": True, "require_issue_created_after_lookback": False},
        },
        limits=RuntimeLimits(max_repos=None, max_prs=None, max_cases=10, max_cases_per_repo=10, max_seconds=None),
    )
    repo = {"full_name": "owner/repo"}
    pr = {
        "number": 7,
        "merged_at": "2026-06-01T00:00:00Z",
        "updated_at": "2026-06-01T00:00:00Z",
        "user": {"login": "human"},
        "title": "Fixes #1",
        "body": "Fixes #1",
        "head": {"ref": "fix-1"},
    }
    case_count, repo_case_count = _process_pr(db=db, gh=IssueTooShortGH(), settings=settings, repo=repo, pr=pr, start=0, case_count=0, repo_case_count=0)
    assert case_count == 0
    assert repo_case_count == 0
    assert db.exclusions[-1][3] == "issue_body_too_short"
