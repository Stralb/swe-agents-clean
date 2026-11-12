from __future__ import annotations

import re
from typing import Iterable

try:
    from langdetect import detect_langs
except Exception:  # pragma: no cover
    detect_langs = None


def word_count(text: str | None) -> int:
    if not text:
        return 0
    return len(re.findall(r"\b\w+\b", text))


def is_probably_english(text: str | None) -> bool:
    if not text or not text.strip():
        return False
    if detect_langs is None:
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
        return ascii_ratio > 0.85
    try:
        langs = detect_langs(text[:4000])
        return any(str(l.lang) == "en" and float(l.prob) >= 0.70 for l in langs)
    except Exception:
        ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
        return ascii_ratio > 0.85


def contains_any(text: str | None, needles: Iterable[str]) -> list[str]:
    if not text:
        return []
    lower = text.lower()
    return [n for n in needles if n.lower() in lower]


def short(text: str | None, n: int = 240) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned if len(cleaned) <= n else cleaned[: n - 1] + "..."
