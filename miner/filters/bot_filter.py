from __future__ import annotations


def is_excluded_bot(author: str | None, title: str | None, branch: str | None, bot_terms: list[str]) -> bool:
    hay = " ".join([author or "", title or "", branch or ""]).lower()
    return any(term.lower() in hay for term in bot_terms)
