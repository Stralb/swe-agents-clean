from __future__ import annotations
from miner.github.stop_control import cooperative_sleep

import logging
import time
from pathlib import Path
from typing import Mapping

from miner.db.database import Database

log = logging.getLogger(__name__)

class RateLimitManager:
    """SQLite-backed GitHub rate-limit tracker for continuous mining.

    GitHub has separate buckets for core and search. A single global reserve is
    wrong because authenticated search commonly has a limit around 30/minute,
    while core has thousands/hour. The manager therefore applies conservative
    per-resource reserves and only blocks the resource needed by the next call.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        min_remaining: int = 100,
        search_min_remaining: int = 0,
        enabled: bool = True,
    ):
        self.db = Database(db_path) if db_path else None
        self.min_remaining = max(0, int(min_remaining or 0))
        self.search_min_remaining = max(0, int(search_min_remaining or 0))
        self.enabled = enabled and self.db is not None

    def reserve_for(self, resource: str, limit_value: int | None = None) -> int:
        resource = (resource or "core").lower()
        limit_i = int(limit_value or 0)
        if resource == "search":
            # Search limit is small and fast-resetting. Keep only a tiny reserve;
            # never apply the core reserve of 100 to the search bucket.
            if limit_i > 0:
                return min(self.search_min_remaining, max(0, limit_i // 10))
            return self.search_min_remaining
        return self.min_remaining

    def update_from_headers(self, headers: Mapping[str, str], *, message: str = "") -> None:
        if not self.enabled or self.db is None:
            return
        remaining = headers.get("X-RateLimit-Remaining") or headers.get("x-ratelimit-remaining")
        limit = headers.get("X-RateLimit-Limit") or headers.get("x-ratelimit-limit")
        reset = headers.get("X-RateLimit-Reset") or headers.get("x-ratelimit-reset")
        resource = headers.get("X-RateLimit-Resource") or headers.get("x-ratelimit-resource") or "core"
        if remaining is None or reset is None:
            return
        try:
            remaining_i = int(remaining)
            limit_i = int(limit or 0)
            reset_i = int(reset)
        except ValueError:
            return
        self.db.execute(
            """
            INSERT INTO github_rate_limits(resource, limit_value, remaining, reset_at, updated_at, last_message)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            ON CONFLICT(resource) DO UPDATE SET
                limit_value=excluded.limit_value,
                remaining=excluded.remaining,
                reset_at=excluded.reset_at,
                updated_at=CURRENT_TIMESTAMP,
                last_message=excluded.last_message
            """,
            (resource, limit_i, remaining_i, reset_i, message[:500]),
        )

    def seconds_until_safe(self, resource_hint: str = "core") -> int:
        if not self.enabled or self.db is None:
            return 0
        resource_hint = (resource_hint or "core").lower()
        row = self.db.one(
            "SELECT resource, limit_value, remaining, reset_at FROM github_rate_limits WHERE resource=?",
            (resource_hint,),
        )
        if not row:
            return 0
        now = int(time.time())
        remaining = int(row.get("remaining") or 0)
        limit_value = int(row.get("limit_value") or 0)
        reserve = self.reserve_for(resource_hint, limit_value)
        # If reserve is 0, only sleep once the bucket is truly empty.
        # This avoids the old behaviour where the 30/min search bucket caused
        # constant near-startup sleep spam.
        if reserve <= 0:
            if remaining <= 0:
                return max(int(row.get("reset_at") or now) - now + 2, 1)
            return 0
        if remaining <= reserve:
            return max(int(row.get("reset_at") or now) - now + 2, 1)
        return 0

    def wait_if_needed(self, resource_hint: str = "core") -> None:
        wait = self.seconds_until_safe(resource_hint)
        if wait <= 0:
            return
        resource_hint = (resource_hint or "core").lower()
        reserve = self.reserve_for(resource_hint)
        if self.db is not None:
            self.db.execute(
                "UPDATE github_rate_limits SET last_sleep_until=?, last_message=? WHERE resource=?",
                (int(time.time()) + wait, f"Sleeping to preserve {resource_hint} reserve of {reserve} GitHub requests", resource_hint),
            )
        if wait > 5:
            log.warning("GitHub %s rate budget is low; sleeping %ss before next %s API call", resource_hint, wait, resource_hint)
        else:
            log.debug("GitHub %s rate budget is low; sleeping %ss", resource_hint, wait)
        cooperative_sleep(wait)
