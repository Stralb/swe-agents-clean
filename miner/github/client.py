from __future__ import annotations
from miner.github.stop_control import CooperativeStopRequested, cooperative_sleep

import math
import os
import sqlite3

import hashlib
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from miner.github.rate_limit import RateLimitManager

log = logging.getLogger(__name__)


class GitHubAPIError(RuntimeError):
    """Raised for GitHub API failures with status/body preserved for resilient callers."""

    def __init__(self, url: str, status_code: int, body: str):
        self.url = url
        self.status_code = status_code
        self.body = body or ""
        super().__init__(f"GitHub GET {url} failed: {status_code} {self.body[:400]}")


class GitHubSecondaryRateLimit(RuntimeError):
    """Raised when GitHub asks us to slow down search/API calls."""

    def __init__(
        self,
        message: str,
        wait_seconds: int = 90,
        *,
        cooldown_until: int | None = None,
    ):
        super().__init__(message)
        self.wait_seconds = wait_seconds
        self.cooldown_until = cooldown_until



class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        timeout: int = 30,
        cache_dir: str | Path | None = None,
        cache_enabled: bool = True,
        force_refresh: bool = False,
        secondary_wait_seconds: int = 90,
        max_secondary_retries: int = 2,
        rate_db_path: str | Path | None = None,
        min_remaining: int = 0,
        search_min_remaining: int = 0,
        search_min_interval_seconds: float = 2.25,
        core_min_interval_seconds: float = 0.0,
        jitter_seconds: float = 0.5,
        secondary_cooldown_path: str | Path | None = None,
        secondary_cooldown_base_seconds: int = 300,
        secondary_cooldown_max_seconds: int = 3600,
    ):
        self.session = requests.Session()
        self.timeout = timeout
        self.base = "https://api.github.com"
        self.cache_enabled = cache_enabled
        self.force_refresh = force_refresh
        self.secondary_wait_seconds = secondary_wait_seconds
        self.max_secondary_retries = max_secondary_retries
        self.max_transient_retries = 3
        self.search_min_interval_seconds = max(0.0, float(search_min_interval_seconds or 0.0))
        self.core_min_interval_seconds = max(0.0, float(core_min_interval_seconds or 0.0))
        self.jitter_seconds = max(0.0, float(jitter_seconds or 0.0))
        self.secondary_cooldown_path = (
            Path(secondary_cooldown_path)
            if secondary_cooldown_path
            else None
        )
        self.secondary_cooldown_base_seconds = max(
            60,
            int(secondary_cooldown_base_seconds or 300),
        )
        self.secondary_cooldown_max_seconds = max(
            self.secondary_cooldown_base_seconds,
            int(secondary_cooldown_max_seconds or 3600),
        )
        self._last_request_at: dict[str, float] = {}
        self.rate_limiter = RateLimitManager(
            rate_db_path,
            min_remaining=min_remaining,
            search_min_remaining=search_min_remaining,
            enabled=bool(rate_db_path and (min_remaining > 0 or search_min_remaining > 0)),
        )
        self.cache_dir = Path(cache_dir or "data/cache/github_api")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.tokens = [t.strip() for t in re.split(r"[,;\s]+", token or "") if t.strip()]
        # The SQLite rate-limit table is keyed only by resource,
        # not by PAT/account. With multiple accounts it can contain
        # stale exhausted state from a different token and block all
        # tokens before response-based rotation can occur.
        if len(self.tokens) > 1:
            self.rate_limiter.enabled = False
        self._token_index = 0
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.session.headers.update(headers)
        self._apply_token(0)

    def _apply_token(self, index: int) -> bool:
        if not self.tokens:
            self.session.headers.pop("Authorization", None)
            return False
        self._token_index = index % len(self.tokens)
        self.session.headers["Authorization"] = f"Bearer {self.tokens[self._token_index]}"
        return True

    def _rotate_token(self) -> bool:
        if len(self.tokens) <= 1:
            return False
        old = self._token_index
        self._apply_token(old + 1)
        log.warning("Rotated GitHub token after rate/auth pressure: token %s -> %s of %s", old + 1, self._token_index + 1, len(self.tokens))
        return True

    def _cache_key(self, url: str, params: dict[str, Any] | None) -> Path:
        canonical = url
        if params:
            canonical += "?" + urlencode(sorted((str(k), str(v)) for k, v in params.items()))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.json"

    def _is_secondary_rate_limit(self, resp: requests.Response) -> bool:
        if resp.status_code != 403:
            return False
        text = (resp.text or "").lower()
        return "secondary rate limit" in text or "abuse detection" in text or "please wait a few minutes" in text

    def _secondary_wait_from_response(self, resp: requests.Response) -> int:
        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return max(int(retry_after), self.secondary_wait_seconds)
        return self.secondary_wait_seconds

    def _read_secondary_cooldown(self) -> dict[str, Any]:
        path = self.secondary_cooldown_path
        if path is None or not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            log.warning("Ignoring unreadable GitHub cooldown file %s", path)
            return {}

    def _raise_if_secondary_cooldown_active(self) -> None:
        payload = self._read_secondary_cooldown()
        until = int(payload.get("until") or 0)
        remaining = max(0, int(math.ceil(until - time.time())))
        if remaining <= 0:
            return
        raise GitHubSecondaryRateLimit(
            (
                "GitHub global secondary-rate cooldown is active; "
                f"wait_seconds={remaining}; cooldown_until={until}; "
                f"trigger_request_id={payload.get('request_id') or 'unknown'}"
            ),
            wait_seconds=remaining,
            cooldown_until=until,
        )

    def _activate_secondary_cooldown(
        self,
        *,
        response_wait: int,
        request_context: str,
        request_id: str | None,
    ) -> tuple[int, int]:
        """Atomically publish a process-wide exponential cooldown."""
        now = int(time.time())
        path = self.secondary_cooldown_path
        if path is None:
            wait = max(response_wait, self.secondary_cooldown_base_seconds)
            return wait, now + wait

        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.with_suffix(path.suffix + ".lock")
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            try:
                import fcntl

                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            except (ImportError, OSError):
                pass

            current = self._read_secondary_cooldown()
            current_until = int(current.get("until") or 0)
            if current_until > now:
                return current_until - now, current_until

            last_triggered = int(current.get("last_triggered_at") or 0)
            prior_count = int(current.get("consecutive_count") or 0)
            if now - last_triggered > 6 * 60 * 60:
                prior_count = 0
            count = prior_count + 1
            exponential = self.secondary_cooldown_base_seconds * (2 ** (count - 1))
            wait = max(response_wait, min(exponential, self.secondary_cooldown_max_seconds))
            wait = min(
                self.secondary_cooldown_max_seconds,
                wait + int(random.uniform(0, min(60, max(1, wait // 10)))),
            )
            until = now + wait
            payload = {
                "version": 1,
                "until": until,
                "wait_seconds": wait,
                "consecutive_count": count,
                "last_triggered_at": now,
                "request_id": request_id,
                "request": request_context[:4000],
            }
            tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
            os.replace(tmp, path)
            return wait, until

    def _is_transient_github_failure(self, resp: requests.Response) -> bool:
        text = (resp.text or "").lower()
        if resp.status_code in {500, 502, 503, 504}:
            return True
        # GitHub sometimes returns this for very large PR file lists/diffs. It is
        # not a methodological failure and must not kill a long overnight run.
        if resp.status_code == 422 and ("diff is taking too long" in text or "diff" in text and "not_available" in text):
            return True
        return False

    @staticmethod
    def is_search_1000_limit_error(exc: BaseException) -> bool:
        """GitHub Search API exposes only the first 1000 results for any query.

        This is an API window boundary, not a collection failure. Callers should
        stop paginating the current search query and continue the run with the
        results already collected.
        """
        return (
            isinstance(exc, GitHubAPIError)
            and exc.status_code == 422
            and "only the first 1000 search results are available" in exc.body.lower()
        )

    def _pace_request(self, resource_hint: str) -> None:
        """Client-side pacing to avoid GitHub secondary rate limits.

        GitHub search has a tiny/minute bucket compared with core API.  The
        miner's repo-first methodology can still issue many searches quickly,
        so every uncached search request is spaced out.  Cached responses return
        before this method and do not consume pacing time.
        """
        min_interval = self.search_min_interval_seconds if resource_hint == "search" else self.core_min_interval_seconds
        if min_interval <= 0:
            return
        now = time.time()
        last = self._last_request_at.get(resource_hint, 0.0)
        wait = (last + min_interval) - now
        if wait > 0:
            if self.jitter_seconds > 0:
                wait += random.uniform(0, self.jitter_seconds)
            log.debug("Pacing GitHub %s request for %.2fs", resource_hint, wait)
            cooperative_sleep(wait)
        self._last_request_at[resource_hint] = time.time()

    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> Any:
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        cache_path = self._cache_key(url, params)
        if self.cache_enabled and not self.force_refresh and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)["data"]

        attempt = 0
        resource_hint = "search" if "/search/" in url else "core"
        while True:
            self._raise_if_secondary_cooldown_active()
            self.rate_limiter.wait_if_needed(resource_hint)
            self._pace_request(resource_hint)
            resp = self.session.get(url, params=params, timeout=self.timeout)
            self.rate_limiter.update_from_headers(resp.headers, message=f"GET {url}")
            if resp.status_code == 401:
                if self._rotate_token():
                    continue
                raise RuntimeError("GitHub token rejected. Rotate the token and set it via .env or GH_TOKEN=...; token hidden.")
            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                if self._rotate_token():
                    continue
                reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                sleep_for = max(reset - int(time.time()) + 2, 1)
                auth_state = "authenticated" if self.session.headers.get("Authorization") else "unauthenticated"
                # Overnight runs should pause and resume instead of dying at 3am.
                log.warning(
                    "GitHub primary rate limit reached (%s). Sleeping %ss until reset, then retrying %s",
                    auth_state,
                    sleep_for,
                    url,
                )
                cooperative_sleep(sleep_for)
                continue
            if self._is_secondary_rate_limit(resp):
                response_wait = self._secondary_wait_from_response(resp)

                request_context = json.dumps(
                    {
                        "method": "GET",
                        "url": url,
                        "resource": resource_hint,
                        "params": params or {},
                        "status": resp.status_code,
                        "remaining": resp.headers.get(
                            "X-RateLimit-Remaining"
                        ),
                        "limit": resp.headers.get(
                            "X-RateLimit-Limit"
                        ),
                        "reset": resp.headers.get(
                            "X-RateLimit-Reset"
                        ),
                        "retry_after": resp.headers.get(
                            "Retry-After"
                        ),
                        "request_id": resp.headers.get(
                            "X-GitHub-Request-Id"
                        ),
                        "message": (resp.text or "")[:1000],
                    },
                    sort_keys=True,
                    default=str,
                )

                wait, until = self._activate_secondary_cooldown(
                    response_wait=response_wait,
                    request_context=request_context,
                    request_id=resp.headers.get("X-GitHub-Request-Id"),
                )
                raise GitHubSecondaryRateLimit(
                    (
                        "GitHub secondary rate limit; entire mining pass deferred "
                        f"without retry; wait_seconds={wait}; cooldown_until={until}; "
                        f"request={request_context}"
                    ),
                    wait_seconds=wait,
                    cooldown_until=until,
                )
            if resp.status_code >= 400:
                if self._is_transient_github_failure(resp) and attempt < self.max_transient_retries:
                    attempt += 1
                    wait = min(5 * (2 ** (attempt - 1)), 60)
                    log.warning(
                        "GitHub transient API failure %s for %s; sleeping %ss before retry %s/%s",
                        resp.status_code,
                        url,
                        wait,
                        attempt,
                        self.max_transient_retries,
                    )
                    cooperative_sleep(wait)
                    continue
                raise GitHubAPIError(url, resp.status_code, resp.text[:2000])
            data = resp.json()
            if self.cache_enabled:
                tmp = cache_path.with_suffix(".tmp")
                with tmp.open("w", encoding="utf-8") as f:
                    json.dump({"url": url, "params": params or {}, "cached_at": time.time(), "data": data}, f)
                tmp.replace(cache_path)
            return data

    def paginate(self, path: str, params: dict[str, Any] | None = None, max_pages: int | None = None, start_page: int = 1):
        """Yield paginated API items.

        ``max_pages`` is the number of pages to fetch in this call, not an
        absolute GitHub page number. The earlier implementation compared the
        absolute page to ``max_pages``; combined with resumed ``start_page`` and
        MAX_SEARCH_TERMS/MAX_PAGES values this could silently keep retrieval
        state stuck on page 1.
        """
        page = max(1, int(start_page or 1))
        pages_seen = 0
        page_limit = None if max_pages is None else max(1, int(max_pages or 1))
        params = dict(params or {})
        params.setdefault("per_page", 50)
        while True:
            if page_limit is not None and pages_seen >= page_limit:
                break
            params["page"] = page
            try:
                data = self.get(path, params)
            except GitHubAPIError as exc:
                if self.is_search_1000_limit_error(exc):
                    log.warning(
                        "GitHub search window ended at page %s for %s. Only first 1000 results are available; continuing with collected results.",
                        page,
                        path,
                    )
                    break
                raise
            if not data:
                break
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
            else:
                items = data
            pages_seen += 1
            for item in items:
                yield item
            if len(items) < params.get("per_page", 50):
                break
            page += 1

    def search_repos(self, query: str, per_page: int = 50):
        # GitHub Search caps access to 1000 results per query. Avoid requesting
        # page 11 when per_page=100 or page 21 when per_page=50.
        safe_per_page = max(1, min(int(per_page or 50), 100))
        max_pages = max(1, 1000 // safe_per_page)
        yield from self.paginate(
            "/search/repositories",
            {"q": query, "sort": "stars", "order": "desc", "per_page": safe_per_page},
            max_pages=max_pages,
        )

    def search_issues(self, query: str, per_page: int = 50, max_pages: int | None = None, start_page: int = 1):
        safe_per_page = max(1, min(int(per_page or 50), 100))
        search_cap_pages = max(1, 1000 // safe_per_page)
        effective_max_pages = min(max_pages, search_cap_pages) if max_pages else search_cap_pages
        yield from self.paginate(
            "/search/issues",
            {"q": query, "sort": "updated", "order": "desc", "per_page": safe_per_page},
            max_pages=effective_max_pages,
            start_page=start_page,
        )


    def search_issues_page(
        self,
        query: str,
        per_page: int = 100,
        page: int = 1,
    ) -> dict[str, Any]:
        """Fetch one GitHub issue-search page with count metadata.

        Adaptive date partitioning needs ``total_count`` before deciding
        whether a query window can be retrieved directly or must be split.
        This method performs exactly one search request.
        """
        safe_per_page = max(
            1,
            min(int(per_page or 100), 100),
        )
        safe_page = max(1, int(page or 1))

        data = self.get(
            "/search/issues",
            {
                "q": query,
                "sort": "updated",
                "order": "desc",
                "per_page": safe_per_page,
                "page": safe_page,
            },
        )

        if not isinstance(data, dict):
            items = list(data or [])
            return {
                "total_count": len(items),
                "incomplete_results": False,
                "items": items,
            }

        return {
            "total_count": int(
                data.get("total_count")
                or 0
            ),
            "incomplete_results": bool(
                data.get("incomplete_results")
                or False
            ),
            "items": list(
                data.get("items")
                or []
            ),
        }

    def closed_pulls(
        self,
        repo_full_name: str,
        *,
        per_page: int = 100,
        max_pages: int = 2,
    ):
        """List closed PRs through the core API, avoiding Search throttling."""
        safe_per_page = max(1, min(int(per_page or 100), 100))
        yield from self.paginate(
            f"/repos/{repo_full_name}/pulls",
            {
                "state": "closed",
                "sort": "updated",
                "direction": "desc",
                "per_page": safe_per_page,
            },
            max_pages=max(1, int(max_pages or 1)),
        )


    def graphql(self, query: str, variables: dict[str, Any] | None = None) -> Any:
        """Execute a GitHub GraphQL query with the same cache/rate-limit policy as REST.

        Used by the downstream-first collector to hydrate PR candidates with
        same-repository closing issue references and changed-file paths in one
        lightweight request. Callers should still use REST pull files when they
        need unified diff patches, because GraphQL file nodes do not include the
        patch text required by the scanners.
        """
        url = "https://api.github.com/graphql"
        payload = {"query": query, "variables": variables or {}}
        cache_path = self._cache_key(url, {"payload": json.dumps(payload, sort_keys=True)})
        if self.cache_enabled and not self.force_refresh and cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as f:
                return json.load(f)["data"]

        attempt = 0
        while True:
            self._raise_if_secondary_cooldown_active()
            self.rate_limiter.wait_if_needed("core")
            self._pace_request("core")
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            self.rate_limiter.update_from_headers(resp.headers, message="POST GitHub GraphQL")
            if resp.status_code == 401:
                if self._rotate_token():
                    continue
                raise RuntimeError("GitHub token rejected. Rotate the token and set it via .env or GH_TOKEN=...; token hidden.")
            if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
                if self._rotate_token():
                    continue
                reset = int(resp.headers.get("X-RateLimit-Reset", "0"))
                sleep_for = max(reset - int(time.time()) + 2, 1)
                log.warning("GitHub GraphQL primary rate limit reached. Sleeping %ss until reset", sleep_for)
                cooperative_sleep(sleep_for)
                continue
            if self._is_secondary_rate_limit(resp):
                response_wait = self._secondary_wait_from_response(resp)
                context = json.dumps(
                    {
                        "method": "POST",
                        "url": url,
                        "resource": "graphql",
                        "status": resp.status_code,
                        "remaining": resp.headers.get("X-RateLimit-Remaining"),
                        "request_id": resp.headers.get("X-GitHub-Request-Id"),
                        "message": (resp.text or "")[:1000],
                    },
                    sort_keys=True,
                )
                wait, until = self._activate_secondary_cooldown(
                    response_wait=response_wait,
                    request_context=context,
                    request_id=resp.headers.get("X-GitHub-Request-Id"),
                )
                raise GitHubSecondaryRateLimit(
                    (
                        "GitHub GraphQL secondary rate limit; entire mining pass "
                        f"deferred without retry; wait_seconds={wait}; "
                        f"cooldown_until={until}; request={context}"
                    ),
                    wait_seconds=wait,
                    cooldown_until=until,
                )
            if resp.status_code >= 400:
                raise GitHubAPIError(url, resp.status_code, resp.text[:2000])
            data = resp.json()
            if data.get("errors"):
                raise GitHubAPIError(url, 200, json.dumps(data.get("errors"), ensure_ascii=False)[:2000])
            if self.cache_enabled:
                tmp = cache_path.with_suffix(".tmp")
                with tmp.open("w", encoding="utf-8") as f:
                    json.dump({"url": url, "params": {"graphql": True}, "cached_at": time.time(), "data": data}, f)
                tmp.replace(cache_path)
            return data

    def rate_limit(self) -> Any:
        old_cache = self.cache_enabled
        self.cache_enabled = False
        try:
            return self.get("/rate_limit")
        finally:
            self.cache_enabled = old_cache
