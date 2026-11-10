from __future__ import annotations

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _rendered_markdown(at: AppTest) -> str:
    return "\n".join(str(m.value) for m in at.markdown)


def test_streamlit_overview_renders_without_exceptions():
    at = AppTest.from_file("ui/app.py")
    at.run(timeout=20)
    assert not at.exception
    rendered = _rendered_markdown(at)
    for heading in (
        "Issue links",
        "AI agents",
        "Dependency",
        "CI/CD secrets",
        "Source security",
        "Issue steering",
        "Security regression",
    ):
        assert heading in rendered


def test_ui_removes_native_page_clutter_and_theme_toggle():
    at = AppTest.from_file("ui/app.py")
    at.run(timeout=20)
    rendered = _rendered_markdown(at)
    radio_labels = [r.label for r in at.radio]
    assert "Theme" not in radio_labels
    assert "Navigation" in radio_labels
    assert "exports" not in rendered.lower()
    assert "tag manager" not in rendered.lower()
    assert "compact-metrics" in rendered
    assert "signal-strip" in rendered
    assert "Source-code" in rendered
    assert "Secret/CI" in rendered
    assert "Dependency" in rendered
    assert "stream-grid" in rendered
    assert "stream-card" in rendered
    assert "query-chip-link" in rendered
    assert "sidebar-db-card" in rendered
    assert "worker-panel" in rendered or "Workers" not in rendered
    assert "Second review" not in rendered
