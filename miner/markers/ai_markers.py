from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re


@dataclass
class AIMarker:
    marker_text: str
    marker_location: str
    confidence: str
    matched_tool: str | None = None


def _marker_matches(text: str, marker: str) -> bool:
    marker = (marker or "").strip()
    if not marker:
        return False
    # Path/bot/provenance markers are intentionally matched literally.
    if any(ch in marker for ch in "/[]:@"):
        return marker.lower() in text.lower()
    # Plain tool names/phrases require token boundaries so Devin does not match widevine.
    pattern = r"(?<![A-Za-z0-9_])" + re.escape(marker) + r"(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def _scan_text(text: str | None, markers: Iterable[str], confidence: str, location: str) -> list[AIMarker]:
    if not text:
        return []
    hits = []
    seen: set[tuple[str, str]] = set()
    for marker in markers:
        if _marker_matches(text, str(marker)):
            key = (str(marker).lower(), location)
            if key not in seen:
                seen.add(key)
                hits.append(AIMarker(marker_text=str(marker), marker_location=location, confidence=confidence, matched_tool=str(marker)))
    return hits


def detect_ai_markers(candidate_texts: dict[str, str | None], config: dict) -> tuple[str, list[AIMarker]]:
    ai_cfg = config.get("ai_markers", {})
    high = ai_cfg.get("high_confidence", []) or []
    medium = ai_cfg.get("medium_confidence", []) or []
    hits: list[AIMarker] = []
    for loc, text in candidate_texts.items():
        hits.extend(_scan_text(text, high, "high", loc))
        hits.extend(_scan_text(text, medium, "medium", loc))
    if any(h.confidence == "high" for h in hits):
        return "AI-explicit-high", hits
    if hits:
        return "AI-explicit-medium", hits
    return "AI-unknown", []
