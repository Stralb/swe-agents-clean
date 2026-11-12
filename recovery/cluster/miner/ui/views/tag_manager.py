from __future__ import annotations

import streamlit as st

from src.db.database import Database


def render_tag_manager(settings) -> None:
    db = Database(settings.db_path)
    st.header("Tag manager")
    tags = db.query("SELECT id, name, type, description FROM tags ORDER BY type, name")
    st.dataframe(tags, width="stretch", hide_index=True)

    st.subheader("Create manual tag")
    name = st.text_input("Tag name")
    desc = st.text_input("Description")
    if st.button("Create tag") and name:
        db.execute("INSERT OR IGNORE INTO tags(name, type, description) VALUES (?, 'manual', ?)", (name, desc))
        st.success("Tag created")
        st.rerun()

    st.subheader("Rename/delete tag")
    manual_tags = db.query("SELECT id, name FROM tags WHERE type='manual' ORDER BY name")
    names = [t["name"] for t in manual_tags]
    selected = st.selectbox("Select manual tag", names) if names else None
    if selected:
        new_name = st.text_input("New name", selected)
        col1, col2 = st.columns(2)
        if col1.button("Rename"):
            db.execute("UPDATE tags SET name=? WHERE name=? AND type='manual'", (new_name, selected))
            st.success("Renamed")
            st.rerun()
        if col2.button("Delete"):
            tag = db.one("SELECT id FROM tags WHERE name=?", (selected,))
            if tag:
                db.execute("DELETE FROM case_tags WHERE tag_id=?", (tag["id"],))
                db.execute("DELETE FROM tags WHERE id=?", (tag["id"],))
            st.success("Deleted")
            st.rerun()
