from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AgenticIndicator:
    key: str
    agent: str
    query_fragment: str
    marker_text: str
    marker_location: str
    head_prefix: str | None = None
    author_login: str | None = None
    body_phrase: str | None = None
    required_author: str | None = None


@dataclass(frozen=True)
class AgenticQueryJob:
    # Kept for compatibility with collection logging and stream keys.
    language: str
    indicator: AgenticIndicator
    query: str


AGENTIC_INDICATORS: tuple[AgenticIndicator, ...] = (
    AgenticIndicator(
        key="codex_head",
        agent="OpenAI Codex",
        query_fragment="head:codex/",
        marker_text="codex/",
        marker_location="pr_branch",
        head_prefix="codex/",
    ),
    AgenticIndicator(
        key="devin_author",
        agent="Devin",
        query_fragment="author:devin-ai-integration[bot]",
        marker_text="devin-ai-integration[bot]",
        marker_location="pr_author",
        author_login="devin-ai-integration[bot]",
    ),
    AgenticIndicator(
        key="copilot_head_author",
        agent="GitHub Copilot",
        query_fragment="head:copilot/",
        marker_text="copilot/",
        marker_location="pr_branch",
        head_prefix="copilot/",
        required_author="copilot",
    ),
    AgenticIndicator(
        key="cursor_head",
        agent="Cursor",
        query_fragment="head:cursor/",
        marker_text="cursor/",
        marker_location="pr_branch",
        head_prefix="cursor/",
    ),
    AgenticIndicator(
        key="claude_coauthor_body",
        agent="Claude Code",
        query_fragment='"Co-Authored-By: Claude" in:body',
        marker_text="Co-Authored-By: Claude",
        marker_location="pr_body",
        body_phrase="Co-Authored-By: Claude",
    ),
    AgenticIndicator(
        key="claude_generated_body",
        agent="Claude Code",
        query_fragment='"Generated with Claude Code" in:body',
        marker_text="Generated with Claude Code",
        marker_location="pr_body",
        body_phrase="Generated with Claude Code",
    ),
)


def _maintenance_exclusions(authors: Iterable[str]) -> str:
    seen: set[str] = set()
    exclusions: list[str] = []

    for raw_author in authors:
        author = str(raw_author or "").strip()
        key = author.lower()

        if not author or key in seen:
            continue

        seen.add(key)
        exclusions.append(f"-author:{author}")

    return " ".join(exclusions)


def build_agentic_query_jobs(
    *,
    languages: Iterable[str],
    min_stars: int,
    merged_since: str,
    maintenance_authors: Iterable[str],
) -> list[AgenticQueryJob]:
    """Build one query per approved agentic indicator.

    GitHub issue/PR search performs marker, merge-date and linked-issue
    discovery. Repository stars and JS/TS changed-file scope are validated
    after each result is hydrated.
    """

    configured_languages = {
        str(language).strip().lower()
        for language in languages
        if str(language).strip()
    }

    if not configured_languages.intersection({"javascript", "typescript"}):
        raise ValueError(
            "Agentic JS/TS discovery requires JavaScript or TypeScript"
        )

    if int(min_stars) < 0:
        raise ValueError("min_stars cannot be negative")

    exclusions = _maintenance_exclusions(maintenance_authors)

    base = (
        "is:pr is:merged linked:issue "
        "archived:false draft:false "
        f"merged:>={merged_since}"
    )

    return [
        AgenticQueryJob(
            language="javascript-typescript",
            indicator=indicator,
            query=(
                f"{base} {indicator.query_fragment} {exclusions}"
            ).strip(),
        )
        for indicator in AGENTIC_INDICATORS
    ]


def validate_pr_for_job(
    pr: dict,
    job: AgenticQueryJob,
) -> tuple[bool, str]:
    indicator = job.indicator
    author = str(
        (pr.get("user") or {}).get("login") or ""
    ).strip()
    head_ref = str(
        (pr.get("head") or {}).get("ref") or ""
    ).strip()
    body = str(pr.get("body") or "")

    if indicator.head_prefix and not head_ref.lower().startswith(
        indicator.head_prefix.lower()
    ):
        return (
            False,
            f"expected head prefix {indicator.head_prefix!r}; "
            f"actual head_ref={head_ref!r}",
        )

    if indicator.author_login and author.lower() != (
        indicator.author_login.lower()
    ):
        return (
            False,
            f"expected author {indicator.author_login!r}; "
            f"actual author={author!r}",
        )

    if indicator.required_author and author.lower() != (
        indicator.required_author.lower()
    ):
        return (
            False,
            f"expected verified author "
            f"{indicator.required_author!r}; "
            f"actual author={author!r}",
        )

    if indicator.body_phrase and indicator.body_phrase.lower() not in (
        body.lower()
    ):
        return (
            False,
            f"expected PR-body phrase "
            f"{indicator.body_phrase!r}",
        )

    return True, "ok"
