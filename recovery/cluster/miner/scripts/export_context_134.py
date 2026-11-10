#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests


ROOT = Path(
    "/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart"
)

DB = (
    ROOT
    / "data"
    / "miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db"
)

OUT = ROOT / "data" / "context_enrichment_134"
CACHE = OUT / "api_cache"

CONTEXT_CSV = OUT / "context_134.csv"
SOURCES_JSONL = OUT / "context_sources_134.jsonl"
QC_JSON = OUT / "context_qc_summary.json"
MANIFEST_JSON = OUT / "context_manifest.json"

BUNDLE = (
    ROOT
    / "data"
    / "context_enrichment_134_bundle.zip"
)

EXCLUDED = {
    59,
    8038,
    8162,
    10825,
}

EXPECTED_CASES = 134

# Keep the same GitHub API version used by the mining codebase.
API_VERSION = "2022-11-28"

OUT.mkdir(
    parents=True,
    exist_ok=True,
)

CACHE.mkdir(
    parents=True,
    exist_ok=True,
)


def parse_dt(
    value: str | None,
) -> datetime | None:

    if not value:
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        dt = datetime.fromisoformat(
            text
        )

    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


def hours_between(
    start: str | None,
    end: str | None,
) -> float | None:

    a = parse_dt(
        start
    )

    b = parse_dt(
        end
    )

    if (
        a is None
        or b is None
    ):
        return None

    return round(
        (
            b - a
        ).total_seconds()
        / 3600.0,
        3,
    )


def days_between(
    start: str | None,
    end: str | None,
) -> float | None:

    a = parse_dt(
        start
    )

    b = parse_dt(
        end
    )

    if (
        a is None
        or b is None
    ):
        return None

    return round(
        (
            b - a
        ).total_seconds()
        / 86400.0,
        3,
    )


def read_env_tokens() -> list[str]:

    values: list[str] = []

    for key in (
        "GITHUB_TOKENS",
        "GITHUB_TOKEN",
        "GH_TOKEN",
    ):
        raw = os.getenv(
            key
        )

        if raw:
            values.append(
                raw
            )

    env_path = (
        ROOT
        / ".env.cluster"
    )

    if env_path.exists():

        for raw_line in env_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():

            line = (
                raw_line
                .strip()
            )

            if (
                not line
                or line.startswith("#")
            ):
                continue

            if line.startswith(
                "export "
            ):
                line = (
                    line[7:]
                    .strip()
                )

            if "=" not in line:
                continue

            key, value = (
                line.split(
                    "=",
                    1,
                )
            )

            key = key.strip()

            if key not in {
                "GITHUB_TOKENS",
                "GITHUB_TOKEN",
                "GH_TOKEN",
            }:
                continue

            value = (
                value
                .strip()
                .strip('"')
                .strip("'")
            )

            if value:
                values.append(
                    value
                )

    if (
        not values
        and shutil.which(
            "gh"
        )
    ):
        result = subprocess.run(
            [
                "gh",
                "auth",
                "token",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
        )

        if (
            result.returncode == 0
            and result.stdout.strip()
        ):
            values.append(
                result.stdout.strip()
            )

    tokens: list[str] = []
    seen: set[str] = set()

    for value in values:

        for token in re.split(
            r"[,;\s]+",
            value,
        ):
            token = token.strip()

            if (
                token
                and token not in seen
            ):
                seen.add(
                    token
                )

                tokens.append(
                    token
                )

    return tokens


class GitHubAPI:

    def __init__(
        self,
        tokens: list[str],
    ):

        if not tokens:
            raise RuntimeError(
                "No GitHub token found in "
                "GITHUB_TOKENS/GITHUB_TOKEN/GH_TOKEN, "
                ".env.cluster, or gh auth token."
            )

        self.tokens = tokens
        self.token_index = 0

        self.session = (
            requests.Session()
        )

        self.session.headers.update(
            {
                "Accept":
                    "application/vnd.github+json",
                "X-GitHub-Api-Version":
                    API_VERSION,
                "User-Agent":
                    "malicious-issue-miner-context-enrichment",
            }
        )

        self._apply_token()


    def _apply_token(
        self,
    ) -> None:

        self.session.headers[
            "Authorization"
        ] = (
            "Bearer "
            + self.tokens[
                self.token_index
            ]
        )


    def _rotate(
        self,
    ) -> bool:

        if len(
            self.tokens
        ) <= 1:
            return False

        old = (
            self.token_index
        )

        self.token_index = (
            self.token_index
            + 1
        ) % len(
            self.tokens
        )

        self._apply_token()

        return (
            self.token_index
            != old
        )


    def _cache_path(
        self,
        path: str,
        params: dict[str, Any]
        | None,
    ) -> Path:

        canonical = path

        if params:

            canonical += (
                "?"
                + urlencode(
                    sorted(
                        (
                            str(k),
                            str(v),
                        )
                        for k, v
                        in params.items()
                    )
                )
            )

        digest = hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            CACHE
            / f"{digest}.json"
        )


    def get(
        self,
        path: str,
        params: dict[str, Any]
        | None = None,
    ) -> tuple[
        int,
        Any,
        dict[str, str],
    ]:

        params = dict(
            params
            or {}
        )

        cache_path = (
            self._cache_path(
                path,
                params,
            )
        )

        if cache_path.exists():

            try:
                cached = json.loads(
                    cache_path.read_text(
                        encoding="utf-8"
                    )
                )

                return (
                    int(
                        cached[
                            "status"
                        ]
                    ),
                    cached.get(
                        "data"
                    ),
                    dict(
                        cached.get(
                            "headers"
                        )
                        or {}
                    ),
                )

            except Exception:
                pass

        url = (
            path
            if path.startswith(
                "http"
            )
            else (
                "https://api.github.com"
                + path
            )
        )

        last_error = ""

        for attempt in range(
            1,
            7,
        ):

            try:
                response = (
                    self.session.get(
                        url,
                        params=params,
                        timeout=60,
                    )
                )

            except requests.RequestException as exc:

                last_error = str(
                    exc
                )

                time.sleep(
                    min(
                        5 * attempt,
                        30,
                    )
                )

                continue

            headers = {
                "Link":
                    response.headers.get(
                        "Link",
                        "",
                    ),
                "X-RateLimit-Limit":
                    response.headers.get(
                        "X-RateLimit-Limit",
                        "",
                    ),
                "X-RateLimit-Remaining":
                    response.headers.get(
                        "X-RateLimit-Remaining",
                        "",
                    ),
                "X-RateLimit-Reset":
                    response.headers.get(
                        "X-RateLimit-Reset",
                        "",
                    ),
                "X-GitHub-Request-Id":
                    response.headers.get(
                        "X-GitHub-Request-Id",
                        "",
                    ),
            }

            try:
                data = (
                    response.json()
                )

            except ValueError:
                data = {
                    "message":
                        response.text[
                            :2000
                        ]
                }

            if response.status_code in (
                200,
                404,
            ):

                cache_path.write_text(
                    json.dumps(
                        {
                            "status":
                                response.status_code,
                            "url":
                                url,
                            "params":
                                params,
                            "headers":
                                headers,
                            "data":
                                data,
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )

                return (
                    response.status_code,
                    data,
                    headers,
                )

            message = ""

            if isinstance(
                data,
                dict,
            ):
                message = str(
                    data.get(
                        "message"
                    )
                    or ""
                )

            remaining = (
                response.headers.get(
                    "X-RateLimit-Remaining"
                )
            )

            if (
                response.status_code
                in (
                    401,
                    403,
                )
                and self._rotate()
            ):
                continue

            if response.status_code in (
                403,
                429,
            ):

                retry_after = (
                    response.headers.get(
                        "Retry-After"
                    )
                )

                if (
                    retry_after
                    and retry_after.isdigit()
                ):
                    wait = (
                        int(
                            retry_after
                        )
                        + 2
                    )

                elif remaining == "0":

                    reset = int(
                        response.headers.get(
                            "X-RateLimit-Reset"
                        )
                        or 0
                    )

                    wait = max(
                        reset
                        - int(
                            time.time()
                        )
                        + 3,
                        5,
                    )

                elif (
                    "secondary rate limit"
                    in message.lower()
                    or "abuse"
                    in message.lower()
                ):
                    wait = 90

                else:
                    wait = min(
                        20 * attempt,
                        120,
                    )

                print(
                    "GitHub rate pressure: "
                    f"sleeping {wait}s "
                    f"for {path}",
                    flush=True,
                )

                time.sleep(
                    wait
                )

                continue

            if (
                response.status_code
                >= 500
            ):

                time.sleep(
                    min(
                        5 * attempt,
                        30,
                    )
                )

                continue

            last_error = (
                f"HTTP "
                f"{response.status_code}: "
                f"{message or response.text[:500]}"
            )

            break

        raise RuntimeError(
            "GitHub GET failed for "
            f"{path}: "
            f"{last_error or 'retry limit reached'}"
        )


def parse_last_page(
    link_header: str,
) -> int | None:

    if not link_header:
        return None

    match = re.search(
        r'<[^>]*[?&]page=(\d+)[^>]*>;\s*rel="last"',
        link_header,
    )

    if not match:
        return None

    return int(
        match.group(1)
    )


def count_prior_repo_items(
    api: GitHubAPI,
    repo: str,
    author: str,
    cutoff: datetime,
) -> int | None:

    if not author:
        return None

    page = 1
    per_page = 100

    while True:

        status, data, headers = (
            api.get(
                f"/repos/{repo}/issues",
                {
                    "state":
                        "all",
                    "creator":
                        author,
                    "sort":
                        "created",
                    "direction":
                        "desc",
                    "per_page":
                        per_page,
                    "page":
                        page,
                },
            )
        )

        if (
            status != 200
            or not isinstance(
                data,
                list,
            )
        ):
            return None

        if not data:
            return 0

        older = 0
        crossed = False

        for item in data:

            created = parse_dt(
                item.get(
                    "created_at"
                )
                if isinstance(
                    item,
                    dict,
                )
                else None
            )

            if (
                created is not None
                and created < cutoff
            ):
                older += 1
                crossed = True

        if crossed:

            last_page = (
                parse_last_page(
                    headers.get(
                        "Link",
                        "",
                    )
                )
            )

            if (
                last_page is None
                or last_page <= page
            ):
                return older

            middle_full_pages = max(
                last_page
                - page
                - 1,
                0,
            )

            total = (
                older
                + middle_full_pages
                * per_page
            )

            (
                status_last,
                data_last,
                _,
            ) = api.get(
                f"/repos/{repo}/issues",
                {
                    "state":
                        "all",
                    "creator":
                        author,
                    "sort":
                        "created",
                    "direction":
                        "desc",
                    "per_page":
                        per_page,
                    "page":
                        last_page,
                },
            )

            if (
                status_last != 200
                or not isinstance(
                    data_last,
                    list,
                )
            ):
                return None

            total += len(
                data_last
            )

            return total

        if len(
            data
        ) < per_page:
            return 0

        page += 1


def human_review_before_merge(
    api: GitHubAPI,
    repo: str,
    pr_number: int,
    pr_author: str | None,
    merged_at: datetime,
) -> tuple[
    bool | None,
    int | None,
]:

    page = 1
    per_page = 100
    count = 0

    while True:

        status, data, _ = (
            api.get(
                f"/repos/{repo}/pulls/{pr_number}/reviews",
                {
                    "per_page":
                        per_page,
                    "page":
                        page,
                },
            )
        )

        if (
            status != 200
            or not isinstance(
                data,
                list,
            )
        ):
            return (
                None,
                None,
            )

        for review in data:

            if not isinstance(
                review,
                dict,
            ):
                continue

            submitted = parse_dt(
                review.get(
                    "submitted_at"
                )
            )

            if (
                submitted is None
                or submitted
                > merged_at
            ):
                continue

            user = (
                review.get(
                    "user"
                )
                or {}
            )

            login = str(
                user.get(
                    "login"
                )
                or ""
            ).strip()

            user_type = str(
                user.get(
                    "type"
                )
                or ""
            ).strip().lower()

            is_bot = (
                user_type
                == "bot"
                or login.lower()
                .endswith(
                    "[bot]"
                )
            )

            is_pr_author = bool(
                pr_author
                and login
                and login.lower()
                == str(
                    pr_author
                ).lower()
            )

            if (
                is_bot
                or is_pr_author
            ):
                continue

            count += 1

        if len(
            data
        ) < per_page:

            return (
                count > 0,
                count,
            )

        page += 1


def tool_for_marker(
    marker_text: str,
    matched_tool: str | None,
) -> str:

    value = (
        f"{matched_tool or ''} "
        f"{marker_text or ''}"
    ).lower()

    if (
        "devin-ai-integration"
        in value
        or re.search(
            r"\bdevin\b",
            value,
        )
    ):
        return "Devin"

    if (
        "codex/"
        in value
        or re.search(
            r"\bcodex\b",
            value,
        )
    ):
        return "OpenAI Codex"

    if (
        "copilot/"
        in value
        or "github copilot"
        in value
        or re.search(
            r"\bcopilot\b",
            value,
        )
    ):
        return "GitHub Copilot"

    if (
        "cursor/"
        in value
        or re.search(
            r"\bcursor\b",
            value,
        )
    ):
        return "Cursor"

    if "claude" in value:
        return "Claude Code"

    return str(
        matched_tool
        or marker_text
        or "Unknown"
    ).strip()


def provenance_rank(
    location: str,
) -> int:

    return {
        "pr_author": 0,
        "pr_branch": 1,
        "pr_body": 2,
        "issue_title": 3,
        "issue_body": 3,
    }.get(
        location,
        9,
    )


def evidence_label(
    hits: list[
        dict[str, Any]
    ],
) -> str:

    locations = {
        str(
            hit.get(
                "marker_location"
            )
            or ""
        )
        for hit in hits
    }

    texts = " ".join(
        str(
            hit.get(
                "marker_text"
            )
            or ""
        )
        for hit in hits
    ).lower()

    if "pr_author" in locations:
        return "pr_author_bot"

    if "pr_branch" in locations:
        return "pr_branch_prefix"

    if "pr_body" in locations:

        if (
            "co-authored-by: claude"
            in texts
        ):
            return (
                "pr_body_coauthor"
            )

        if (
            "generated with claude code"
            in texts
        ):
            return (
                "pr_body_generation_marker"
            )

        return (
            "pr_body_marker"
        )

    if locations == {
        "issue_title"
    }:
        return (
            "issue_title_only"
        )

    return (
        "issue_text_only"
    )


def primary_agent(
    markers: list[
        dict[str, Any]
    ],
) -> tuple[
    str | None,
    str | None,
    list[
        dict[str, Any]
    ],
]:

    unique: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for marker in markers:

        text = str(
            marker.get(
                "marker_text"
            )
            or ""
        ).strip()

        location = str(
            marker.get(
                "marker_location"
            )
            or ""
        ).strip()

        if (
            not text
            or not location
        ):
            continue

        key = (
            text.lower(),
            location.lower(),
        )

        if key not in unique:

            unique[
                key
            ] = {
                "marker_text":
                    text,
                "marker_location":
                    location,
                "confidence":
                    marker.get(
                        "confidence"
                    ),
                "matched_tool":
                    marker.get(
                        "matched_tool"
                    ),
                "tool":
                    tool_for_marker(
                        text,
                        marker.get(
                            "matched_tool"
                        ),
                    ),
            }

    dedup = sorted(
        unique.values(),
        key=lambda x: (
            provenance_rank(
                str(
                    x[
                        "marker_location"
                    ]
                )
            ),
            str(
                x[
                    "tool"
                ]
            ),
            str(
                x[
                    "marker_text"
                ]
            ),
        ),
    )

    if not dedup:
        return (
            None,
            None,
            [],
        )

    best_rank = min(
        provenance_rank(
            str(
                hit[
                    "marker_location"
                ]
            )
        )
        for hit in dedup
    )

    strongest = [
        hit
        for hit in dedup
        if provenance_rank(
            str(
                hit[
                    "marker_location"
                ]
            )
        ) == best_rank
    ]

    tools = sorted(
        {
            str(
                hit[
                    "tool"
                ]
            )
            for hit
            in strongest
        }
    )

    tool = (
        tools[0]
        if len(
            tools
        ) == 1
        else (
            "Ambiguous: "
            + "/".join(
                tools
            )
        )
    )

    return (
        tool,
        evidence_label(
            strongest
        ),
        dedup,
    )


def yes_no(
    value: bool | None,
) -> str:

    if value is None:
        return ""

    return (
        "Yes"
        if value
        else "No"
    )


if not DB.exists():
    raise FileNotFoundError(
        f"Snapshot DB not found: "
        f"{DB}"
    )


tokens = read_env_tokens()

print(
    "GitHub tokens available: "
    f"{len(tokens)}",
    flush=True,
)

api = GitHubAPI(
    tokens
)


conn = sqlite3.connect(
    f"file:{DB.resolve()}?mode=ro",
    uri=True,
)

conn.row_factory = (
    sqlite3.Row
)


cases = conn.execute(
    """
    SELECT DISTINCT
        c.id AS case_id,
        r.full_name AS repo_full_name,

        i.number AS issue_number,
        i.author AS issue_author,
        i.created_at AS issue_created_at,
        i.closed_at AS issue_closed_at,

        p.number AS pr_number,
        p.author AS pr_author,
        p.created_at AS pr_created_at,
        p.closed_at AS pr_closed_at,
        p.merged_at AS pr_merged_at,
        p.merged AS pr_merged

    FROM cases c

    JOIN repos r
      ON r.id = c.repo_id

    JOIN issues i
      ON i.id = c.issue_id

    JOIN pull_requests p
      ON p.id = c.pr_id

    WHERE EXISTS (
        SELECT 1
        FROM scanner_findings sf
        WHERE sf.case_id = c.id
          AND sf.introduced = 1
    )

      AND c.id NOT IN (
          59,
          8038,
          8162,
          10825
      )

    ORDER BY c.id
    """
).fetchall()


if len(
    cases
) != EXPECTED_CASES:

    raise RuntimeError(
        f"Expected "
        f"{EXPECTED_CASES} "
        f"corrected cases, "
        f"found {len(cases)}"
    )


case_ids = [
    int(
        row[
            "case_id"
        ]
    )
    for row in cases
]

placeholders = ",".join(
    "?"
    for _ in case_ids
)


marker_rows = (
    conn.execute(
        f"""
        SELECT
            case_id,
            marker_text,
            marker_location,
            confidence,
            matched_tool
        FROM ai_markers
        WHERE case_id IN (
            {placeholders}
        )
        ORDER BY case_id, id
        """,
        case_ids,
    ).fetchall()
)

conn.close()


markers_by_case: dict[
    int,
    list[
        dict[str, Any]
    ],
] = defaultdict(
    list
)

for row in marker_rows:

    markers_by_case[
        int(
            row[
                "case_id"
            ]
        )
    ].append(
        dict(
            row
        )
    )


records: list[
    dict[str, Any]
] = []

source_records: list[
    dict[str, Any]
] = []

errors: list[
    dict[str, Any]
] = []


for index, row in enumerate(
    cases,
    start=1,
):

    case_id = int(
        row[
            "case_id"
        ]
    )

    repo = str(
        row[
            "repo_full_name"
        ]
    )

    issue_number = int(
        row[
            "issue_number"
        ]
    )

    pr_number = int(
        row[
            "pr_number"
        ]
    )

    issue_created = parse_dt(
        row[
            "issue_created_at"
        ]
    )

    merged_at = parse_dt(
        row[
            "pr_merged_at"
        ]
    )

    print(
        f"[{index:3}/"
        f"{EXPECTED_CASES}] "
        f"case={case_id} "
        f"{repo} "
        f"issue=#{issue_number} "
        f"pr=#{pr_number}",
        flush=True,
    )


    (
        primary_tool,
        provenance_evidence,
        dedup_markers,
    ) = primary_agent(
        markers_by_case.get(
            case_id,
            [],
        )
    )


    issue_association = None
    account_created_at = None
    account_age_days = None
    prior_count = None
    review_present = None
    review_count = None
    api_login = None

    case_errors: list[
        str
    ] = []


    try:

        (
            status,
            issue_payload,
            _,
        ) = api.get(
            f"/repos/{repo}"
            f"/issues/"
            f"{issue_number}"
        )

        if (
            status == 200
            and isinstance(
                issue_payload,
                dict,
            )
        ):

            issue_association = (
                issue_payload.get(
                    "author_association"
                )
            )

            api_user = (
                issue_payload.get(
                    "user"
                )
                or {}
            )

            api_login = str(
                api_user.get(
                    "login"
                )
                or ""
            ).strip() or None

        else:
            case_errors.append(
                "issue_detail_unavailable"
            )

    except Exception as exc:

        case_errors.append(
            "issue_detail_error:"
            + str(
                exc
            )
        )


    if (
        api_login
        and issue_created
        is not None
    ):

        try:

            (
                status,
                user_payload,
                _,
            ) = api.get(
                f"/users/"
                f"{api_login}"
            )

            if (
                status == 200
                and isinstance(
                    user_payload,
                    dict,
                )
            ):

                account_created_at = (
                    user_payload.get(
                        "created_at"
                    )
                )

                account_age_days = (
                    days_between(
                        account_created_at,
                        row[
                            "issue_created_at"
                        ],
                    )
                )

            else:
                case_errors.append(
                    "user_profile_unavailable"
                )

        except Exception as exc:

            case_errors.append(
                "user_profile_error:"
                + str(
                    exc
                )
            )


        try:

            prior_count = (
                count_prior_repo_items(
                    api,
                    repo,
                    api_login,
                    issue_created,
                )
            )

            if prior_count is None:
                case_errors.append(
                    "prior_repo_count_unavailable"
                )

        except Exception as exc:

            case_errors.append(
                "prior_repo_count_error:"
                + str(
                    exc
                )
            )

    else:

        case_errors.append(
            "issue_author_api_login_unavailable"
        )


    if merged_at is not None:

        try:

            (
                review_present,
                review_count,
            ) = (
                human_review_before_merge(
                    api,
                    repo,
                    pr_number,
                    row[
                        "pr_author"
                    ],
                    merged_at,
                )
            )

            if (
                review_present
                is None
            ):
                case_errors.append(
                    "review_data_unavailable"
                )

        except Exception as exc:

            case_errors.append(
                "review_data_error:"
                + str(
                    exc
                )
            )

    else:

        case_errors.append(
            "merged_at_missing"
        )


    same_author = None

    if (
        row[
            "issue_author"
        ]
        and row[
            "pr_author"
        ]
    ):

        same_author = (
            str(
                row[
                    "issue_author"
                ]
            ).lower()
            == str(
                row[
                    "pr_author"
                ]
            ).lower()
        )


    record = {

        "Case ID":
            case_id,

        "Repository":
            repo,

        "Issue Number":
            issue_number,

        "Issue Author":
            row[
                "issue_author"
            ]
            or "",

        "PR Number":
            pr_number,

        "PR Author":
            row[
                "pr_author"
            ]
            or "",

        "Issue Author Account Created (UTC)":
            account_created_at
            or "",

        "Account Age at Issue (Days)":
            (
                account_age_days
                if account_age_days
                is not None
                else ""
            ),

        "Issue Author Association":
            issue_association
            or "",

        "Prior Repo Issues/PRs Before Issue":
            (
                prior_count
                if prior_count
                is not None
                else ""
            ),

        "Same Issue/PR Author":
            yes_no(
                same_author
            ),

        "Issue to PR Creation Delay (Hours)":
            hours_between(
                row[
                    "issue_created_at"
                ],
                row[
                    "pr_created_at"
                ],
            ),

        "Issue Duration (Hours)":
            hours_between(
                row[
                    "issue_created_at"
                ],
                row[
                    "issue_closed_at"
                ],
            ),

        "PR Duration (Hours)":
            hours_between(
                row[
                    "pr_created_at"
                ],
                row[
                    "pr_closed_at"
                ],
            ),

        "PR Time-to-Merge (Hours)":
            hours_between(
                row[
                    "pr_created_at"
                ],
                row[
                    "pr_merged_at"
                ],
            ),

        "Human Review Present Before Merge":
            yes_no(
                review_present
            ),

        "Primary Agentic Tool":
            primary_tool
            or "",

        "Primary Provenance Evidence":
            provenance_evidence
            or "",
    }


    records.append(
        record
    )


    source_records.append(
        {

            "case_id":
                case_id,

            "repo":
                repo,

            "issue_number":
                issue_number,

            "pr_number":
                pr_number,

            "stored_issue_author":
                row[
                    "issue_author"
                ],

            "api_issue_author_login":
                api_login,

            "issue_created_at":
                row[
                    "issue_created_at"
                ],

            "pr_created_at":
                row[
                    "pr_created_at"
                ],

            "pr_merged_at":
                row[
                    "pr_merged_at"
                ],

            "account_created_at":
                account_created_at,

            "issue_author_association":
                issue_association,

            "prior_repo_issues_prs_before_issue":
                prior_count,

            "qualifying_human_review_count_before_merge":
                review_count,

            "deduplicated_ai_markers":
                dedup_markers,

            "errors":
                case_errors,
        }
    )


    if case_errors:

        errors.append(
            {
                "case_id":
                    case_id,
                "errors":
                    case_errors,
            }
        )


fieldnames = list(
    records[
        0
    ].keys()
)


with CONTEXT_CSV.open(
    "w",
    encoding="utf-8",
    newline="",
) as handle:

    writer = csv.DictWriter(
        handle,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    writer.writerows(
        records
    )


with SOURCES_JSONL.open(
    "w",
    encoding="utf-8",
) as handle:

    for record in source_records:

        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )


missing_counts = Counter()


for record in records:

    for field in (

        "Account Age at Issue (Days)",
        "Issue Author Association",
        "Prior Repo Issues/PRs Before Issue",
        "Same Issue/PR Author",
        "Issue to PR Creation Delay (Hours)",
        "PR Time-to-Merge (Hours)",
        "Human Review Present Before Merge",
        "Primary Agentic Tool",
        "Primary Provenance Evidence",

    ):

        if (
            record[
                field
            ] == ""
            or record[
                field
            ] is None
        ):

            missing_counts[
                field
            ] += 1


qc = {

    "case_count":
        len(
            records
        ),

    "unique_case_count":
        len(
            {
                int(
                    r[
                        "Case ID"
                    ]
                )
                for r
                in records
            }
        ),

    "excluded_case_ids":
        sorted(
            EXCLUDED
        ),

    "non_merged_cases":
        [
            int(
                row[
                    "case_id"
                ]
            )
            for row in cases
            if (
                int(
                    row[
                        "pr_merged"
                    ]
                    or 0
                ) != 1
                or not row[
                    "pr_merged_at"
                ]
            )
        ],

    "missing_counts":
        dict(
            missing_counts
        ),

    "cases_with_api_or_enrichment_errors":
        errors,

    "primary_agentic_tool_counts":
        dict(
            Counter(
                str(
                    r[
                        "Primary Agentic Tool"
                    ]
                )
                for r
                in records
            )
        ),

    "primary_provenance_evidence_counts":
        dict(
            Counter(
                str(
                    r[
                        "Primary Provenance Evidence"
                    ]
                )
                for r
                in records
            )
        ),

    "human_review_present_counts":
        dict(
            Counter(
                str(
                    r[
                        "Human Review Present Before Merge"
                    ]
                )
                for r
                in records
            )
        ),

    "author_association_counts":
        dict(
            Counter(
                str(
                    r[
                        "Issue Author Association"
                    ]
                )
                for r
                in records
            )
        ),
}


QC_JSON.write_text(
    json.dumps(
        qc,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


manifest = {

    "created_at_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "source_database":
        DB.name,

    "corrected_positive_case_count":
        EXPECTED_CASES,

    "excluded_false_positive_case_ids":
        sorted(
            EXCLUDED
        ),

    "github_api_version":
        API_VERSION,

    "main_context_fields": [

        "Account Age at Issue (Days)",

        "Issue Author Association",

        "Prior Repo Issues/PRs Before Issue",

        "Same Issue/PR Author",

        "Issue to PR Creation Delay (Hours)",

        "PR Time-to-Merge (Hours)",

        "Human Review Present Before Merge",

        "Primary Agentic Tool",

        "Primary Provenance Evidence",

    ],

    "definitions": {

        "Account Age at Issue (Days)":
            (
                "issue_created_at minus "
                "public GitHub account created_at "
                "for the issue author"
            ),

        "Issue Author Association":
            (
                "GitHub issue author_association "
                "value returned for the issue"
            ),

        "Prior Repo Issues/PRs Before Issue":
            (
                "count of repository issues and "
                "pull requests created by the same "
                "issue author strictly before "
                "issue_created_at"
            ),

        "Same Issue/PR Author":
            (
                "case-insensitive equality of "
                "stored issue author and PR author logins"
            ),

        "Issue to PR Creation Delay (Hours)":
            (
                "PR created_at minus issue created_at; "
                "negative means the PR predates the issue"
            ),

        "PR Time-to-Merge (Hours)":
            (
                "PR merged_at minus PR created_at"
            ),

        "Human Review Present Before Merge":
            (
                "at least one submitted GitHub PR review "
                "at/before merge from a non-bot actor "
                "other than the PR author"
            ),

        "Primary Agentic Tool":
            (
                "tool selected deterministically from "
                "deduplicated AI markers using "
                "PR author > PR branch > "
                "PR body > issue text"
            ),

        "Primary Provenance Evidence":
            (
                "location/type of the strongest evidence "
                "used for Primary Agentic Tool"
            ),
    },

    "not_collected": [

        "followers/following",

        "bio/location/company/email",

        "PR-author account age",

        "reviewer identities as analysis features",

        "CI metrics",

        "suspicion scores",
    ],

    "scanner_details_exported":
        False,
}


MANIFEST_JSON.write_text(
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


with zipfile.ZipFile(
    BUNDLE,
    "w",
    compression=zipfile.ZIP_DEFLATED,
    compresslevel=6,
) as archive:

    for path in (

        CONTEXT_CSV,
        SOURCES_JSONL,
        QC_JSON,
        MANIFEST_JSON,

    ):

        archive.write(
            path,
            path.name,
        )


print()
print(
    "=" * 80
)

print(
    "CONTEXT ENRICHMENT COMPLETE"
)

print(
    "=" * 80
)

print(
    f"Cases: "
    f"{len(records)}"
)

print(
    f"Unique cases: "
    f"{len({int(r['Case ID']) for r in records})}"
)

print(
    "Cases with enrichment "
    f"warnings/errors: "
    f"{len(errors)}"
)

print(
    f"Missing counts: "
    f"{dict(missing_counts)}"
)

print(
    f"Bundle: "
    f"{BUNDLE}"
)

print(
    f"Bundle size: "
    f"{BUNDLE.stat().st_size / 1024**2:.2f} MB"
)

print()
print(
    "Primary tools:"
)

for key, value in sorted(
    qc[
        "primary_agentic_tool_counts"
    ].items(),
    key=lambda x: (
        -x[1],
        x[0],
    ),
):

    print(
        f"  {value:3}  {key}"
    )


print()
print(
    "Provenance evidence:"
)

for key, value in sorted(
    qc[
        "primary_provenance_evidence_counts"
    ].items(),
    key=lambda x: (
        -x[1],
        x[0],
    ),
):

    print(
        f"  {value:3}  {key}"
    )
