from src.markers.ai_markers import detect_ai_markers


def test_ai_marker_high_path_marker():
    cfg = {"ai_markers": {"high_confidence": ["codex/"], "medium_confidence": ["ChatGPT"]}}
    cohort, hits = detect_ai_markers({"branch": "codex/fix-bug"}, cfg)
    assert cohort == "AI-explicit-high"
    assert hits


def test_ai_marker_does_not_substring_match_widevine():
    cfg = {"ai_markers": {"high_confidence": [], "medium_confidence": ["Devin"]}}
    cohort, hits = detect_ai_markers({"issue": "GB News extractor uses widevine metadata"}, cfg)
    assert cohort == "AI-unknown"
    assert hits == []


def test_ai_marker_plain_phrase_uses_boundaries():
    cfg = {"ai_markers": {"high_confidence": [], "medium_confidence": ["Claude Code", "Devin"]}}
    cohort, hits = detect_ai_markers({"body": "Generated with Claude Code"}, cfg)
    assert cohort == "AI-explicit-medium"
    assert [h.marker_text for h in hits] == ["Claude Code"]
