from __future__ import annotations

import streamlit as st


def _pill_class(label: str) -> str:
    low = label.lower()
    if "secret" in low or "vulnerability" in low or "strong" in low:
        return "pill pill-danger"
    if "review" in low or "dependency" in low or "possible" in low:
        return "pill pill-warn"
    if "benign" in low or "clean" in low:
        return "pill pill-good"
    return "pill"


def badge_row(labels: list[str]) -> None:
    if not labels:
        st.caption("No badges")
        return
    html = " ".join([f'<span class="{_pill_class(str(x))}">{str(x)}</span>' for x in labels])
    st.markdown(html, unsafe_allow_html=True)


def json_tags(value: str | None) -> list[str]:
    import json
    if not value:
        return []
    try:
        data = json.loads(value)
        return data if isinstance(data, list) else []
    except Exception:
        return []
