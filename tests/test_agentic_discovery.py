from miner.filters.pr_filters import has_javascript_typescript_surface
from miner.pipeline.agentic_discovery import (
    build_agentic_query_jobs,
    validate_pr_for_job,
)


MAINTENANCE = (
    "dependabot[bot]",
    "renovate[bot]",
    "github-actions[bot]",
)


def _jobs():
    return build_agentic_query_jobs(
        languages=["JavaScript", "TypeScript"],
        min_stars=100,
        merged_since="2025-11-01",
        maintenance_authors=MAINTENANCE,
    )


def test_six_indicator_queries_cover_javascript_and_typescript():
    jobs = _jobs()
    assert len(jobs) == 6
    assert all(job.language == "javascript-typescript" for job in jobs)

    queries = [job.query for job in jobs]
    for query in queries:
        assert "is:pr is:merged linked:issue" in query
        assert "merged:>=2025-11-01" in query
        assert "archived:false" in query
        assert "-author:dependabot[bot]" in query
        assert "-author:renovate[bot]" in query
        assert "language:JavaScript" not in query
        assert "language:TypeScript" not in query
        assert "stars:>=100" not in query


def test_only_approved_agentic_indicators_are_queried():
    queries = "\n".join(job.query for job in _jobs())

    assert "head:codex/" in queries
    assert "author:devin-ai-integration[bot]" in queries
    assert "head:copilot/" in queries
    assert "head:cursor/" in queries
    assert '"Co-Authored-By: Claude" in:body' in queries
    assert '"Generated with Claude Code" in:body' in queries

    for forbidden in (
        "ChatGPT",
        "OpenHands",
        "Cline",
        "Jules",
        "Windsurf",
        "AI-generated",
        "coderabbit",
        "gemini-code-assist",
    ):
        assert forbidden not in queries


def test_copilot_requires_both_branch_and_verified_author():
    job = next(
        job
        for job in _jobs()
        if job.indicator.key == "copilot_head_author"
    )

    valid_pr = {
        "user": {"login": "copilot"},
        "head": {"ref": "copilot/fix-auth"},
        "body": "",
    }
    assert validate_pr_for_job(valid_pr, job)[0] is True

    wrong_author = {
        "user": {"login": "human-user"},
        "head": {"ref": "copilot/fix-auth"},
        "body": "",
    }
    assert validate_pr_for_job(wrong_author, job)[0] is False


def test_cursor_branch_allows_human_pr_author():
    job = next(
        job
        for job in _jobs()
        if job.indicator.key == "cursor_head"
    )

    pr = {
        "user": {"login": "human-user"},
        "head": {"ref": "cursor/implement-parser"},
        "body": "",
    }
    assert validate_pr_for_job(pr, job)[0] is True


def test_claude_marker_must_exist_in_pr_body():
    job = next(
        job
        for job in _jobs()
        if job.indicator.key == "claude_generated_body"
    )

    valid_pr = {
        "user": {"login": "human-user"},
        "head": {"ref": "feature/fix"},
        "body": "Generated with Claude Code",
    }
    assert validate_pr_for_job(valid_pr, job)[0] is True

    invalid_pr = {
        "user": {"login": "human-user"},
        "head": {"ref": "feature/fix"},
        "body": "This PR updates Claude documentation.",
    }
    assert validate_pr_for_job(invalid_pr, job)[0] is False


def test_javascript_typescript_surface_filter():
    assert has_javascript_typescript_surface(
        [{"filename": "src/index.ts"}]
    )
    assert has_javascript_typescript_surface(
        [{"filename": "packages/app/package-lock.json"}]
    )
    assert has_javascript_typescript_surface(
        [{"filename": ".github/workflows/test.yml"}]
    )
    assert has_javascript_typescript_surface(
        [{"filename": "vite.config.js"}]
    )

    assert not has_javascript_typescript_surface(
        [{"filename": "docs/guide.md"}]
    )
    assert not has_javascript_typescript_surface(
        [{"filename": "src/service.py"}]
    )
