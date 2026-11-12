"""In-memory GitHub API replay implementing the recovered miner's read methods.

No requests dependency, network, file access, credentials, SQLite, caches, timers,
or retries. Every API call requires an explicitly supplied response fixture.
This is a testing adapter, not a production HTTP client.
"""
from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Mapping
from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any
from urllib.parse import urlsplit


class MissingFixtureError(LookupError):
    """No recorded response exists for an attempted API call."""


class GitHubAPIError(RuntimeError):
    """Preserves the historical API exception's url/status/body contract."""

    def __init__(self, url: str, status_code: int, body: str):
        self.url = url
        self.status_code = int(status_code)
        self.body = body or ""
        super().__init__(f"GitHub GET {url} failed: {status_code} {self.body[:400]}")


@dataclass(frozen=True)
class FixtureResponse:
    data: Any = None
    status_code: int = 200
    body: str = ""


@dataclass(frozen=True)
class RecordedCall:
    method: str
    path: str
    params: str
    json_body: str


def _canonical_path(value: str) -> str:
    """Accept GitHub API paths or exact api.github.com URLs only; never fetch."""
    if value.startswith("/") and not value.startswith("//"):
        return value
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.netloc.lower() != "api.github.com":
        raise ValueError("Only GitHub API paths or api.github.com URLs are valid replay keys")
    if parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise ValueError("Replay URL must not include credentials, query strings or fragments")
    return parsed.path


def _stable_json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class FixtureTransport:
    """Fail-closed in-memory sequence of synthetic/recorded API responses.

    Any state is confined to this object. It never reads environment variables
    or opens files. Repeated calls to the same request key consume responses
    in the order explicitly registered by the test.
    """

    def __init__(self):
        self._responses: dict[RecordedCall, deque[FixtureResponse]] = {}
        self.calls: list[RecordedCall] = []

    @staticmethod
    def key(
        method: str, path: str, params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> RecordedCall:
        method = str(method).upper()
        if method not in ("GET", "POST"):
            raise ValueError("Replay supports GET and POST only")
        return RecordedCall(method, _canonical_path(path), _stable_json(params), _stable_json(json_body))

    def add(
        self, method: str, path: str, *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
        data: Any = None,
        status_code: int = 200,
        body: str = "",
    ) -> None:
        key = self.key(method, path, params, json_body)
        self._responses.setdefault(key, deque()).append(
            FixtureResponse(deepcopy(data), int(status_code), str(body))
        )

    def request(
        self, method: str, path: str, *,
        params: Mapping[str, Any] | None = None,
        json_body: Mapping[str, Any] | None = None,
    ) -> Any:
        key = self.key(method, path, params, json_body)
        self.calls.append(key)
        queue = self._responses.get(key)
        if not queue:
            raise MissingFixtureError(f"No offline fixture for {key.method} {key.path} with supplied parameters")
        response = queue.popleft()
        if response.status_code >= 400:
            raise GitHubAPIError(
                "https://api.github.com" + key.path,
                response.status_code,
                response.body,
            )
        return deepcopy(response.data)

    def unconsumed_count(self) -> int:
        return sum(len(queue) for queue in self._responses.values())


class ReplayGitHubClient:
    """Collection-facing subset of the historical GitHubClient's read API.

    Intentionally excludes token rotation, rate-budget sleeps, HTTP retries,
    request pacing, on-disk caching and shared cooldown writes. Those are real
    runtime concerns that need separate dependency-injected integration tests.
    """

    def __init__(self, transport: FixtureTransport):
        if not isinstance(transport, FixtureTransport):
            raise TypeError("An explicit FixtureTransport is required; no network fallback exists")
        self.transport = transport

    def get(self, path_or_url: str, params: Mapping[str, Any] | None = None) -> Any:
        return self.transport.request("GET", path_or_url, params=params)

    @staticmethod
    def is_search_1000_limit_error(exc: BaseException) -> bool:
        return (
            isinstance(exc, GitHubAPIError)
            and exc.status_code == 422
            and "only the first 1000 search results are available" in exc.body.lower()
        )

    def paginate(
        self, path: str, params: Mapping[str, Any] | None = None,
        max_pages: int | None = None, start_page: int = 1,
    ) -> Iterator[Any]:
        """Mirror the recovered client: max_pages counts fetched pages, not page ID."""
        page = max(1, int(start_page or 1))
        pages_seen = 0
        limit = None if max_pages is None else max(1, int(max_pages or 1))
        query = dict(params or {})
        query.setdefault("per_page", 50)
        while limit is None or pages_seen < limit:
            query["page"] = page
            try:
                data = self.get(path, query)
            except GitHubAPIError as exc:
                if self.is_search_1000_limit_error(exc):
                    break
                raise
            if not data:
                break
            items = data.get("items") if isinstance(data, dict) and "items" in data else data
            if not isinstance(items, list):
                raise ValueError("Replay pagination expected list or search response with list 'items'")
            pages_seen += 1
            yield from items
            if len(items) < query.get("per_page", 50):
                break
            page += 1

    def search_repos(self, query: str, per_page: int = 50) -> Iterator[Any]:
        size = max(1, min(int(per_page or 50), 100))
        yield from self.paginate(
            "/search/repositories",
            {"q": query, "sort": "stars", "order": "desc", "per_page": size},
            max_pages=max(1, 1000 // size),
        )

    def search_issues(
        self, query: str, per_page: int = 50,
        max_pages: int | None = None, start_page: int = 1,
    ) -> Iterator[Any]:
        size = max(1, min(int(per_page or 50), 100))
        cap = max(1, 1000 // size)
        effective = min(max_pages, cap) if max_pages else cap
        yield from self.paginate(
            "/search/issues",
            {"q": query, "sort": "updated", "order": "desc", "per_page": size},
            max_pages=effective, start_page=start_page,
        )

    def search_issues_page(self, query: str, per_page: int = 100, page: int = 1) -> dict[str, Any]:
        size = max(1, min(int(per_page or 100), 100))
        safe_page = max(1, int(page or 1))
        data = self.get(
            "/search/issues",
            {"q": query, "sort": "updated", "order": "desc", "per_page": size, "page": safe_page},
        )
        if not isinstance(data, dict):
            items = list(data or [])
            return {"total_count": len(items), "incomplete_results": False, "items": items}
        return {
            "total_count": int(data.get("total_count") or 0),
            "incomplete_results": bool(data.get("incomplete_results") or False),
            "items": list(data.get("items") or []),
        }

    def closed_pulls(self, repo_full_name: str, *, per_page: int = 100, max_pages: int = 2) -> Iterator[Any]:
        size = max(1, min(int(per_page or 100), 100))
        yield from self.paginate(
            f"/repos/{repo_full_name}/pulls",
            {"state": "closed", "sort": "updated", "direction": "desc", "per_page": size},
            max_pages=max(1, int(max_pages or 1)),
        )

    def graphql(self, query: str, variables: Mapping[str, Any] | None = None) -> Any:
        result = self.transport.request(
            "POST", "/graphql", json_body={"query": query, "variables": dict(variables or {})},
        )
        if isinstance(result, dict) and result.get("errors"):
            raise GitHubAPIError(
                "https://api.github.com/graphql", 200,
                json.dumps(result["errors"], ensure_ascii=False)[:2000],
            )
        return result

    def rate_limit(self) -> Any:
        return self.get("/rate_limit")
