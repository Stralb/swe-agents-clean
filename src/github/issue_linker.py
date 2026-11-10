from __future__ import annotations

import re
from urllib.parse import urlparse

# Closing keywords are the strongest GitHub-native signal. They may be used with
# bare numbers ("fixes #123") or full issue URLs.
KEYWORD_RE = re.compile(
    r"(?:fixe[sd]?|close[sd]?|resolve[sd]?)\s+"
    r"(?:(https://github\.com/([^/]+)/([^/]+)/issues/(\d+))|#?(\d+))",
    re.I,
)
# Full URLs are useful, but only when they point to this repository. Dependency
# update PRs often embed third-party changelogs containing many unrelated issue
# URLs, which must not link to issues in the current repo.
URL_RE = re.compile(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", re.I)
BARE_RE = re.compile(r"(?:issue|bug)\s+#(\d+)", re.I)


def _same_repo(owner: str | None, repo: str | None, current_repo: str | None) -> bool:
    if not owner or not repo or not current_repo:
        # Backward-compatible behavior when no current repo is supplied.
        return True
    return f"{owner}/{repo}".lower() == current_repo.lower()


def find_linked_issue_numbers(*texts: str | None, current_repo: str | None = None) -> list[tuple[int, str]]:
    """Find issue numbers linked from PR metadata.

    The function is intentionally conservative about full GitHub issue URLs:
    only URLs pointing to the current repository are accepted. This prevents
    generated dependency-changelog PRs from linking pytest/numpy/etc. issue
    numbers to unrelated issues that happen to have the same number locally.
    """
    found: dict[int, str] = {}
    for text in texts:
        if not text:
            continue
        for m in KEYWORD_RE.finditer(text):
            owner, repo, url_num, bare_num = m.group(2), m.group(3), m.group(4), m.group(5)
            if url_num is not None:
                if _same_repo(owner, repo, current_repo):
                    found.setdefault(int(url_num), "closing-keyword")
            elif bare_num is not None:
                found.setdefault(int(bare_num), "closing-keyword")

        for m in URL_RE.finditer(text):
            owner, repo, num = m.groups()
            if _same_repo(owner, repo, current_repo):
                found.setdefault(int(num), "issue-url")

        # Keep weak bare references, but only where a human explicitly says
        # "issue #N" or "bug #N". Generic changelog bullets usually do not.
        for m in BARE_RE.finditer(text):
            found.setdefault(int(m.group(1)), "issue-reference")
    return [(num, method) for num, method in found.items()]
