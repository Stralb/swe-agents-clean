"""Deterministic in-memory rate-budget decisions from the archived miner policy.

This is an extracted decision-policy adapter, not the historical SQLite-backed
RateLimitManager. It never sleeps, creates files, accesses the environment or
instantiates a database. All times and headers are passed explicitly.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class RateSnapshot:
    resource: str
    limit_value: int
    remaining: int
    reset_at: int


def parse_rate_headers(headers: Mapping[str, str]) -> RateSnapshot | None:
    """Parse header fields used by original update_from_headers(), or return None."""
    remaining = headers.get("X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
    limit = headers.get("X-RateLimit-Limit") or headers.get("x-ratelimit-limit")
    reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
    resource = headers.get("X-RateLimit-Resource") or headers.get("x-ratelimit-resource") or "core"
    if remaining is None or reset is None:
        return None
    try:
        return RateSnapshot(
            resource=str(resource),
            limit_value=int(limit or 0),
            remaining=int(remaining),
            reset_at=int(reset),
        )
    except (TypeError, ValueError):
        return None


def reserve_for(
    resource: str, *, limit_value: int = 0,
    min_remaining: int = 100, search_min_remaining: int = 0,
) -> int:
    """Mirror historical RateLimitManager.reserve_for without a database."""
    resource = (resource or "core").lower()
    limit_i = int(limit_value or 0)
    core_reserve = max(0, int(min_remaining or 0))
    search_reserve = max(0, int(search_min_remaining or 0))
    if resource == "search":
        if limit_i > 0:
            return min(search_reserve, max(0, limit_i // 10))
        return search_reserve
    return core_reserve


def seconds_until_safe(
    snapshot: RateSnapshot | None, *, now: int,
    min_remaining: int = 100, search_min_remaining: int = 0,
) -> int:
    """Compute historical delay with explicit 'now'; never block or sleep."""
    if snapshot is None:
        return 0
    reserve = reserve_for(
        snapshot.resource, limit_value=snapshot.limit_value,
        min_remaining=min_remaining, search_min_remaining=search_min_remaining,
    )
    if reserve <= 0:
        blocked = snapshot.remaining <= 0
    else:
        blocked = snapshot.remaining <= reserve
    if blocked:
        return max(int(snapshot.reset_at) - int(now) + 2, 1)
    return 0
