"""Pure historic-style repository and lookback gates for offline collector fixtures.

Mirrors the recovered Oct-2026 `_repo_passes_universe`, `_lookback_start`,
`_lookback_months`, `_iso_dt`, and `_within_lookback` decision semantics.
To make relative time reproducible, months require an explicit aware UTC clock.
Historical naive PR/issue timestamps used the *host's* local time zone; rather
than silently changing their meaning, this adapter refuses naive timestamps
when a lookback comparison is requested.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

SECONDS_PER_HISTORICAL_MONTH = 31 * 24 * 60 * 60


def positive_lookback_months(value: Any) -> int | None:
    """Match the historical config parser: non-positive/invalid -> no months."""
    try:
        months = int(value)
    except (TypeError, ValueError):
        return None
    return months if months > 0 else None


def lookback_start_datetime(value: str | None) -> datetime | None:
    """Match the original UTC interpretation of a naive configured start."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def require_explicit_lookback_clock(
    months: int | None,
    start: datetime | None,
    *,
    reference_now_utc: datetime | None,
) -> None:
    """Reject uncontrolled wall-clock dependence before any fixture or DB I/O."""
    if start is not None or not months:
        return
    if reference_now_utc is None:
        raise ValueError("A timezone-aware reference_now_utc is required for month-based lookback")
    if reference_now_utc.tzinfo is None or reference_now_utc.utcoffset() is None:
        raise ValueError("reference_now_utc must have a timezone offset")


def within_lookback(
    value: str | None,
    *,
    months: int | None = None,
    start: datetime | None = None,
    reference_now_utc: datetime | None = None,
) -> bool:
    """Compare like the original using timestamp seconds and 31-day months.

    Original `_within_lookback` returns True for missing/malformed timestamps,
    even when a lookback gate is configured. This behaviour is preserved.
    """
    dt = _timestamp(value)
    if dt is None:
        return True
    if start is None and not months:
        return True
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(
            "Naive event timestamp has host-dependent historical semantics; "
            "provide ISO-8601 timezone offset in fixture"
        )
    if start is not None:
        return dt.timestamp() >= start.timestamp()
    require_explicit_lookback_clock(months, start, reference_now_utc=reference_now_utc)
    assert reference_now_utc is not None
    cutoff = reference_now_utc.timestamp() - int(months) * SECONDS_PER_HISTORICAL_MONTH
    return dt.timestamp() >= cutoff


def repo_passes_universe(
    repo: Mapping[str, Any], *, configured_min_stars: int = 200,
) -> tuple[bool, str]:
    """Reproduce the original repo-wide screening order, including `or 200`."""
    min_stars = int(configured_min_stars or 200)
    if repo.get("archived"):
        return False, "repo_filter:archived"
    if repo.get("fork"):
        return False, "repo_filter:fork"
    if int(repo.get("stargazers_count") or repo.get("stars") or 0) < min_stars:
        return False, f"repo_filter:stars_below_{min_stars}"
    if repo.get("has_issues") is False:
        return False, "repo_filter:issues_disabled"
    return True, "ok"
