from __future__ import annotations

import pandas as pd
import streamlit as st

from src.db.database import Database
from src.pipeline.case_exporter import selected_evidence_zip, selected_summary_csv
from src.pipeline.export_pipeline import export_cases


CASES_QUERY = """
SELECT
    c.id AS case_id,
    r.full_name AS repo,
    i.title AS issue_title,
    p.title AS pr_title,
    c.ai_cohort,
    c.downstream_signal,
    c.status,
    c.final_label
FROM cases c
JOIN repos r ON c.repo_id = r.id
JOIN issues i ON c.issue_id = i.id
JOIN pull_requests p ON c.pr_id = p.id
ORDER BY c.id DESC
"""


def render_exports(settings) -> None:
    st.header("Exports")
    db = Database(settings.db_path)
    rows = db.query(CASES_QUERY)

    c1, c2 = st.columns([1, 3])
    if c1.button("Write full CSV/JSON to data/exports", type="primary"):
        out = export_cases(settings.db_path)
        st.success(f"Exported {out}")
    c2.caption("For sharing in meetings, use the evidence ZIP: it includes Markdown + JSON per case.")

    if not rows:
        st.info("No cases found yet.")
        return

    df = pd.DataFrame(rows)
    st.markdown("### Select cases to download")
    event = st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        selection_mode="multi-row",
        on_select="rerun",
    )
    try:
        selected_ids = [int(df.iloc[idx]["case_id"]) for idx in event.selection.rows]
    except Exception:
        selected_ids = []

    ids = selected_ids or [int(r["case_id"]) for r in rows]
    label = "selected" if selected_ids else "all"
    d1, d2 = st.columns(2)
    d1.download_button(
        f"Download {label} CSV",
        data=selected_summary_csv(db, ids),
        file_name=f"cases_{label}.csv",
        mime="text/csv",
        width="stretch",
    )
    d2.download_button(
        f"Download {label} evidence ZIP",
        data=selected_evidence_zip(db, ids),
        file_name=f"cases_{label}_evidence.zip",
        mime="application/zip",
        width="stretch",
    )

    st.caption("Select rows to export a subset. With no selection, the buttons export all cases.")
