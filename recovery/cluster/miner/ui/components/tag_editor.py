from __future__ import annotations

import streamlit as st
from src.db.database import Database


def render_tag_editor(db: Database, case_id: int) -> None:
    all_tags = db.query("SELECT id, name FROM tags WHERE type='manual' ORDER BY name")
    case_tags = db.query("SELECT t.id, t.name FROM case_tags ct JOIN tags t ON ct.tag_id=t.id WHERE ct.case_id=? ORDER BY t.name", (case_id,))
    current = {t["name"] for t in case_tags}
    names = [t["name"] for t in all_tags]
    st.markdown("### Manual observations")
    selected = st.multiselect("Manual tags", options=names, default=sorted(current), help="Editable research observations. These are separate from final labels.")
    if st.button("Save tags", key=f"save_tags_{case_id}"):
        db.execute("DELETE FROM case_tags WHERE case_id=?", (case_id,))
        lookup = {t["name"]: t["id"] for t in all_tags}
        for name in selected:
            tag_id = lookup.get(name)
            if tag_id:
                db.execute("INSERT OR IGNORE INTO case_tags(case_id, tag_id) VALUES (?, ?)", (case_id, tag_id))
        st.success("Tags saved")
