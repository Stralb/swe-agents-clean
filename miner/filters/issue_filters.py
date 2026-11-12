from __future__ import annotations

from miner.utils.text import is_probably_english, word_count


def passes_issue_filters(issue: dict, min_words: int, english_only: bool) -> tuple[bool, dict]:
    text = f"{issue.get('title') or ''}\n{issue.get('body') or ''}"
    wc = word_count(issue.get("body") or "")
    en = is_probably_english(text) if english_only else True
    ok = wc >= min_words and en
    return ok, {"word_count": wc, "is_english": en}
