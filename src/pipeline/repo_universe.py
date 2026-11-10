from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

DEFAULT_STAR_BANDS: tuple[tuple[int, int | None], ...] = (
    (200, 499),
    (500, 999),
    (1000, 4999),
    (5000, 9999),
    (10000, None),
)

MAINTENANCE_BOT_AUTHORS = (
    "dependabot[bot]",
    "renovate[bot]",
    "github-actions[bot]",
    "pre-commit-ci[bot]",
    "mergify[bot]",
    "pyup-bot",
    "pyup[bot]",
)


@dataclass(frozen=True)
class MonthWindow:
    start: str
    end: str


def star_band_queries(*, language: str = "Python", pushed_since: str = "2024-01-01", bands: Iterable[tuple[int, int | None]] = DEFAULT_STAR_BANDS) -> list[str]:
    queries: list[str] = []
    for low, high in bands:
        star_expr = f"{low}..{high}" if high is not None else f">={low}"
        queries.append(f"language:{language} stars:{star_expr} archived:false fork:false pushed:>={pushed_since}")
    return queries


def _add_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def month_windows(start: str, months: int) -> list[MonthWindow]:
    start_date = datetime.fromisoformat(start).date().replace(day=1)
    out: list[MonthWindow] = []
    cur = start_date
    for _ in range(max(1, int(months or 1))):
        nxt = _add_month(cur)
        out.append(MonthWindow(start=cur.isoformat(), end=nxt.isoformat()))
        cur = nxt
    return out


def maintenance_bot_exclusions(authors: Iterable[str] = MAINTENANCE_BOT_AUTHORS) -> str:
    return " ".join(f"-author:{a}" for a in authors if a)


def repo_month_pr_query(repo_full_name: str, window: MonthWindow, *, bot_authors: Iterable[str] = MAINTENANCE_BOT_AUTHORS) -> str:
    bots = maintenance_bot_exclusions(bot_authors)
    return f"repo:{repo_full_name} is:pr is:merged linked:issue draft:false merged:{window.start}..{window.end} {bots}".strip()


def lookback_window(start: str, months: int) -> MonthWindow:
    """Return one inclusive/exclusive search window covering the configured lookback.

    This keeps discovery cheap: one GitHub search per repo first, with optional
    month splitting only for unusually busy repositories.
    """
    windows = month_windows(start, months)
    return MonthWindow(start=windows[0].start, end=windows[-1].end)


def repo_window_pr_query(repo_full_name: str, window: MonthWindow, *, bot_authors: Iterable[str] = MAINTENANCE_BOT_AUTHORS) -> str:
    bots = maintenance_bot_exclusions(bot_authors)
    return f"repo:{repo_full_name} is:pr is:merged linked:issue draft:false merged:{window.start}..{window.end} {bots}".strip()


def shard_accept(value: str, *, shard_count: int = 1, shard_index: int = 0) -> bool:
    shard_count = max(1, int(shard_count or 1))
    shard_index = int(shard_index or 0)
    if shard_count <= 1:
        return True
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    bucket = int(digest[:12], 16) % shard_count
    return bucket == shard_index % shard_count


def global_active_pr_query(window: MonthWindow, *, language: str = "Python", min_stars: int = 200, bot_authors: Iterable[str] = MAINTENANCE_BOT_AUTHORS) -> str:
    """Structural global PR search used only to seed active repositories.

    This is not an issue-keyword bucket. It finds repositories that are already
    producing merged issue-linked PRs in the target window, then the normal
    repo-scoped collector performs the actual candidate construction.
    """
    bots = maintenance_bot_exclusions(bot_authors)
    return f"is:pr is:merged linked:issue language:{language} stars:>={int(min_stars)} archived:false draft:false merged:{window.start}..{window.end} {bots}".strip()
