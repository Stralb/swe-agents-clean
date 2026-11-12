from __future__ import annotations

import pandas as pd
import streamlit as st


def render_case_table(rows: list[dict]) -> int | None:
    if not rows:
        st.info("No cases match the current filters.")
        return None
    df = pd.DataFrame(rows)
    display_cols = ["case_id", "repo", "issue_title", "pr_title", "downstream_signal", "ai_cohort", "auto_tags", "status", "final_label"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols], width="stretch", hide_index=True)
    selected = st.number_input("Open case id", min_value=1, step=1, value=int(df.iloc[0]["case_id"]))
    return int(selected) if selected else None
