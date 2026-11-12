from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.db.database import Database
from src.pipeline.case_exporter import (
    selected_evidence_zip,
)
from ui.views.insight_data import (
    case_rows_for_ids,
    load_patterns,
    pattern_breakdown,
)


FAMILY_ORDER = (
    "Region",
    "Mapping rule",
    "Scanner route",
    "File fact",
    "Path rule",
    "Linguist context",
    "AI indicator",
    "Unknown pattern",
)

FAMILY_COLORS = {
    "Region": "#2563eb",
    "Mapping rule": "#7c3aed",
    "Scanner route": "#0891b2",
    "File fact": "#16a34a",
    "Path rule": "#d97706",
    "Linguist context": "#0f766e",
    "AI indicator": "#db2777",
    "Unknown pattern": "#64748b",
}


def _event_pattern_id(
    event: Any,
) -> str | None:
    if event is None:
        return None

    try:
        selection = event.get(
            "selection",
            {},
        )
    except Exception:
        try:
            selection = event.selection
        except Exception:
            return None

    if not isinstance(
        selection,
        dict,
    ):
        return None

    value = selection.get(
        "pattern_pick"
    )

    if isinstance(value, list) and value:
        item = value[0]

        if isinstance(item, dict):
            candidate = item.get(
                "pattern_id"
            )

            if candidate:
                return str(candidate)

    if isinstance(value, dict):
        candidate = value.get(
            "pattern_id"
        )

        if isinstance(candidate, list):
            return (
                str(candidate[0])
                if candidate
                else None
            )

        if candidate:
            return str(candidate)

    return None


def _evidence_columns(
    frame: pd.DataFrame,
    evidence_type: str,
) -> tuple[str, str, str]:
    if evidence_type == "Security only":
        return (
            "security",
            "security_yield_pct",
            "coverage_pct",
        )

    if evidence_type == "Quality/style only":
        return (
            "quality",
            "quality_yield_pct",
            "coverage_pct",
        )

    if evidence_type == "Manually confirmed":
        return (
            "manual_positive",
            "manual_yield_pct",
            "manual_coverage_pct",
        )

    return (
        "introduced",
        "introduced_yield_pct",
        "coverage_pct",
    )


def render_research_map(
    db_path: str,
) -> None:
    patterns = load_patterns(
        db_path
    )

    if not patterns:
        st.info(
            "No persisted mapping patterns "
            "are available yet."
        )
        return

    frame = pd.DataFrame(
        patterns
    )

    controls = st.columns(
        [
            1.35,
            1.25,
            1.35,
            1,
        ]
    )

    family = controls[0].selectbox(
        "Pattern layer",
        [
            "All",
            *[
                value
                for value in FAMILY_ORDER
                if value
                in set(
                    frame["family"]
                )
            ],
        ],
        key="research_pattern_family",
        help=(
            "Filter the map to one level of "
            "the candidate → file fact → region "
            "→ scanner-route pipeline."
        ),
    )

    view = controls[1].selectbox(
        "Map view",
        [
            "Coverage vs yield",
            "Scale vs yield",
        ],
        key="research_map_view",
        help=(
            "Coverage view finds under-tested "
            "promising patterns. Scale view "
            "shows reach across cases and repos."
        ),
    )

    evidence_type = controls[2].selectbox(
        "Positive evidence",
        [
            "Any introduced finding",
            "Security only",
            "Quality/style only",
            "Manually confirmed",
        ],
        key="research_evidence_type",
        help=(
            "Changes the numerator used for "
            "yield. Scanner evidence and manual "
            "confirmation remain separate."
        ),
    )

    maximum_support = max(
        1,
        int(
            frame["cases"].max()
        ),
    )

    default_support = min(
        5,
        maximum_support,
    )

    minimum_support = controls[3].number_input(
        "Minimum cases",
        min_value=1,
        max_value=max(
            1,
            maximum_support,
        ),
        value=max(
            1,
            default_support,
        ),
        step=1,
        key="research_minimum_support",
        help=(
            "Suppress one-off patterns that "
            "could create misleading early yield."
        ),
    )

    if family != "All":
        frame = frame.loc[
            frame["family"] == family
        ].copy()

    frame = frame.loc[
        frame["cases"]
        >= int(minimum_support)
    ].copy()

    if frame.empty:
        st.info(
            "No patterns meet the current "
            "support threshold."
        )
        return

    positive_column, yield_column, coverage_column = (
        _evidence_columns(
            frame,
            evidence_type,
        )
    )

    frame["positive"] = frame[
        positive_column
    ]

    frame["yield"] = frame[
        yield_column
    ]

    frame["coverage"] = frame[
        coverage_column
    ]

    frame["scanner_routes"] = frame[
        "scanners"
    ].apply(
        lambda values: (
            ", ".join(values)
            if isinstance(
                values,
                list,
            )
            and values
            else "Manual / no stored route"
        )
    )

    frame["sample"] = frame.apply(
        lambda row: (
            f"{int(row['scanned'])}/"
            f"{int(row['cases'])}"
            if evidence_type
            != "Manually confirmed"
            else
            f"{int(row['reviewed'])}/"
            f"{int(row['cases'])}"
        ),
        axis=1,
    )

    family_domain = [
        value
        for value in FAMILY_ORDER
        if value in set(
            frame["family"]
        )
    ]

    family_range = [
        FAMILY_COLORS[value]
        for value in family_domain
    ]

    selection = alt.selection_point(
        name="pattern_pick",
        fields=[
            "pattern_id",
        ],
        on="click",
        clear="dblclick",
        empty=False,
    )

    if view == "Scale vs yield":
        x_encoding = alt.X(
            "cases:Q",
            title="Matching cases",
            scale=alt.Scale(
                type="log",
                nice=True,
            ),
        )

        size_encoding = alt.Size(
            "repositories:Q",
            title="Repositories",
            scale=alt.Scale(
                range=[
                    90,
                    1800,
                ]
            ),
        )
    else:
        x_encoding = alt.X(
            "coverage:Q",
            title="Eligible coverage (%)",
            scale=alt.Scale(
                domain=[
                    0,
                    100,
                ]
            ),
        )

        size_encoding = alt.Size(
            "cases:Q",
            title="Matching cases",
            scale=alt.Scale(
                range=[
                    90,
                    1800,
                ]
            ),
        )

    chart = (
        alt.Chart(frame)
        .mark_circle(
            stroke="#ffffff",
            strokeWidth=1.2,
        )
        .encode(
            x=x_encoding,
            y=alt.Y(
                "yield:Q",
                title=(
                    evidence_type
                    + " yield (%)"
                ),
                scale=alt.Scale(
                    domain=[
                        0,
                        max(
                            100,
                            float(
                                frame[
                                    "yield"
                                ].max()
                            ),
                        ),
                    ]
                ),
            ),
            size=size_encoding,
            color=alt.Color(
                "family:N",
                scale=alt.Scale(
                    domain=family_domain,
                    range=family_range,
                ),
                legend=alt.Legend(
                    title=None,
                    orient="bottom",
                ),
            ),
            opacity=alt.condition(
                selection,
                alt.value(1.0),
                alt.Opacity(
                    "confidence:N",
                    scale=alt.Scale(
                        domain=[
                            "Low sample",
                            "Emerging",
                            "Moderate",
                            "Higher support",
                        ],
                        range=[
                            0.42,
                            0.58,
                            0.75,
                            0.9,
                        ],
                    ),
                    legend=None,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "name:N",
                    title="Pattern",
                ),
                alt.Tooltip(
                    "family:N",
                    title="Layer",
                ),
                alt.Tooltip(
                    "cases:Q",
                    title="Cases",
                    format=",",
                ),
                alt.Tooltip(
                    "repositories:Q",
                    title="Repositories",
                    format=",",
                ),
                alt.Tooltip(
                    "sample:N",
                    title="Covered / eligible",
                ),
                alt.Tooltip(
                    "coverage:Q",
                    title="Coverage %",
                    format=".1f",
                ),
                alt.Tooltip(
                    "positive:Q",
                    title="Positive cases",
                    format=",",
                ),
                alt.Tooltip(
                    "yield:Q",
                    title="Yield %",
                    format=".1f",
                ),
                alt.Tooltip(
                    "needs_review:Q",
                    title="Needs review",
                    format=",",
                ),
                alt.Tooltip(
                    "scanner_routes:N",
                    title="Scanners",
                ),
                alt.Tooltip(
                    "confidence:N",
                    title="Sample support",
                ),
            ],
        )
        .add_params(selection)
        .properties(
            height=480,
        )
        .interactive()
    )

    chart_key = (
        "research-evidence-map-"
        + str(
            st.session_state.get(
                "research_chart_nonce",
                0,
            )
        )
    )

    event = None

    try:
        event = st.altair_chart(
            chart,
            width="stretch",
            key=chart_key,
            on_select="rerun",
            selection_mode="pattern_pick",
        )
    except TypeError:
        st.altair_chart(
            chart,
            width="stretch",
            key=chart_key,
        )

    selected_id = _event_pattern_id(
        event
    )

    if selected_id:
        st.session_state[
            "selected_pattern_id"
        ] = selected_id

        st.session_state[
            "research_chart_nonce"
        ] = int(
            st.session_state.get(
                "research_chart_nonce",
                0,
            )
        ) + 1

        st.session_state["nav"] = (
            "Pattern Insights"
        )

        st.rerun()

    fallback = st.selectbox(
        "Open pattern details",
        frame["pattern_id"].tolist(),
        format_func=lambda value: (
            frame.loc[
                frame["pattern_id"]
                == value,
                "family",
            ].iloc[0]
            + " · "
            + frame.loc[
                frame["pattern_id"]
                == value,
                "name",
            ].iloc[0]
        ),
        key="research_pattern_fallback",
        help=(
            "Fallback selector for browsers "
            "that do not return chart-click "
            "events."
        ),
    )

    if st.button(
        "Open selected pattern",
        key="research_open_pattern",
        help=(
            "Open matching cases, mapping "
            "breakdowns and export controls."
        ),
    ):
        st.session_state[
            "selected_pattern_id"
        ] = fallback

        st.session_state["nav"] = (
            "Pattern Insights"
        )

        st.rerun()


def _selected_ids(
    key: str,
) -> set[int]:
    return {
        int(value)
        for value in st.session_state.get(
            key,
            [],
        )
    }


def _set_selected_ids(
    key: str,
    values: set[int],
) -> None:
    st.session_state[key] = sorted(
        values
    )


def _case_table(
    *,
    db_path: str,
    rows: list[dict[str, Any]],
    selection_key: str,
    prefix: str,
) -> None:
    selected = _selected_ids(
        selection_key
    )

    visible_ids = {
        int(row["case_id"])
        for row in rows
    }

    actions = st.columns(
        [
            1.2,
            1.2,
            1.3,
            1.4,
            3,
        ]
    )

    if actions[0].button(
        "Select all",
        key=f"{prefix}-select-all",
    ):
        selected.update(
            visible_ids
        )

        _set_selected_ids(
            selection_key,
            selected,
        )

        st.rerun()

    if actions[1].button(
        "Clear",
        key=f"{prefix}-clear",
    ):
        _set_selected_ids(
            selection_key,
            set(),
        )

        st.session_state.pop(
            f"{prefix}_prepared_zip",
            None,
        )

        st.rerun()

    if actions[2].button(
        "Review selected",
        disabled=not selected,
        key=f"{prefix}-review",
    ):
        queue = sorted(selected)

        st.session_state[
            "review_queue_ids"
        ] = queue

        st.session_state[
            "selected_case_id"
        ] = queue[0]

        st.session_state["nav"] = (
            "Case Review"
        )

        st.rerun()

    if actions[3].button(
        "Prepare ZIP",
        disabled=not selected,
        key=f"{prefix}-prepare",
    ):
        st.session_state[
            f"{prefix}_prepared_zip"
        ] = selected_evidence_zip(
            Database(
                Path(db_path)
            ),
            sorted(selected),
        )

    prepared = st.session_state.get(
        f"{prefix}_prepared_zip"
    )

    if prepared is not None:
        actions[4].download_button(
            "Download selected evidence",
            data=prepared,
            file_name=(
                f"{prefix}_selected_cases.zip"
            ),
            mime="application/zip",
            width="stretch",
            key=f"{prefix}-download",
        )
    else:
        actions[4].markdown(
            f"**{len(selected)} selected**"
        )

    for row in rows:
        case_id = int(
            row["case_id"]
        )

        columns = st.columns(
            [
                0.45,
                0.65,
                1.75,
                4,
                1.65,
                0.8,
                0.8,
                0.85,
            ]
        )

        checked = columns[0].checkbox(
            "Select",
            value=(
                case_id in selected
            ),
            key=(
                f"{prefix}-case-"
                f"{case_id}"
            ),
            label_visibility="collapsed",
        )

        if checked:
            selected.add(case_id)
        else:
            selected.discard(case_id)

        columns[1].markdown(
            f"**#{case_id}**"
        )

        columns[2].write(
            str(
                row.get("repository")
                or ""
            )
        )

        columns[3].write(
            str(
                row.get("issue_title")
                or ""
            )
        )

        columns[4].write(
            str(
                row.get("regions")
                or "Unknown"
            )
        )

        columns[5].write(
            int(
                row.get(
                    "finding_count"
                )
                or 0
            )
        )

        columns[6].write(
            int(
                row.get(
                    "introduced_count"
                )
                or 0
            )
        )

        if columns[7].button(
            "Inspect",
            key=(
                f"{prefix}-inspect-"
                f"{case_id}"
            ),
        ):
            st.session_state[
                "selected_case_id"
            ] = case_id

            st.session_state[
                "review_queue_ids"
            ] = [
                int(item["case_id"])
                for item in rows
            ]

            st.session_state["nav"] = (
                "Case Review"
            )

            st.rerun()

    _set_selected_ids(
        selection_key,
        selected,
    )


def _bar_chart(
    rows: list[dict[str, Any]],
    *,
    title: str,
) -> None:
    if not rows:
        st.info("No data")
        return

    frame = pd.DataFrame(rows)

    chart = (
        alt.Chart(frame)
        .mark_bar(
            cornerRadiusEnd=5,
        )
        .encode(
            y=alt.Y(
                "name:N",
                sort="-x",
                title=None,
            ),
            x=alt.X(
                "value:Q",
                title=title,
            ),
            tooltip=[
                alt.Tooltip(
                    "name:N",
                    title="Value",
                ),
                alt.Tooltip(
                    "value:Q",
                    title=title,
                    format=",",
                ),
            ],
        )
        .properties(
            height=260,
        )
    )

    st.altair_chart(
        chart,
        width="stretch",
    )


def render_pattern_insights(
    settings: Any,
) -> None:
    header, back = st.columns(
        [
            5,
            1,
        ]
    )

    header.title(
        "Pattern Insights"
    )

    if back.button(
        "Back",
        width="stretch",
    ):
        st.session_state["nav"] = (
            "Overview"
        )

        st.rerun()

    pattern_id = str(
        st.session_state.get(
            "selected_pattern_id"
        )
        or ""
    )

    patterns = load_patterns(
        str(settings.db_path)
    )

    pattern = next(
        (
            row
            for row in patterns
            if row["pattern_id"]
            == pattern_id
        ),
        None,
    )

    if pattern is None:
        options = [
            row["pattern_id"]
            for row in patterns
        ]

        if not options:
            st.info(
                "No mapping patterns are "
                "available."
            )
            return

        pattern_id = st.selectbox(
            "Pattern",
            options,
            format_func=lambda value: next(
                (
                    row["family"]
                    + " · "
                    + row["name"]
                    for row in patterns
                    if row[
                        "pattern_id"
                    ] == value
                ),
                value,
            ),
        )

        pattern = next(
            row
            for row in patterns
            if row["pattern_id"]
            == pattern_id
        )

        st.session_state[
            "selected_pattern_id"
        ] = pattern_id

    st.subheader(
        pattern["name"]
    )

    st.caption(
        pattern["family"]
    )

    metrics = st.columns(6)

    metrics[0].metric(
        "Cases",
        pattern["cases"],
    )

    metrics[1].metric(
        "Repositories",
        pattern["repositories"],
    )

    metrics[2].metric(
        "Coverage",
        (
            f"{pattern['coverage_pct']:.1f}%"
        ),
    )

    metrics[3].metric(
        "Introduced yield",
        (
            f"{pattern['introduced_yield_pct']:.1f}%"
        ),
    )

    metrics[4].metric(
        "Security yield",
        (
            f"{pattern['security_yield_pct']:.1f}%"
        ),
    )

    metrics[5].metric(
        "Needs review",
        pattern["needs_review"],
    )

    with st.expander(
        "Mapping definition",
        expanded=False,
    ):
        st.write({
            "layer": pattern["family"],
            "pattern": pattern["name"],
            "mapping_basis": pattern["basis"],
            "scanner_routes": pattern["scanners"],
            "example_paths": pattern["examples"],
            "sample_support": pattern["confidence"],
        })

    breakdown = pattern_breakdown(
        str(settings.db_path),
        pattern["case_ids"],
    )

    tabs = st.tabs([
        "Regions",
        "Scanner routes",
        "Languages",
        "Path rules",
    ])

    with tabs[0]:
        _bar_chart(
            breakdown["regions"],
            title="Cases",
        )

    with tabs[1]:
        _bar_chart(
            breakdown["scanners"],
            title="Cases",
        )

    with tabs[2]:
        _bar_chart(
            breakdown["languages"],
            title="Cases",
        )

    with tabs[3]:
        _bar_chart(
            breakdown["paths"],
            title="Cases",
        )

    st.subheader(
        "Matching cases"
    )

    rows = case_rows_for_ids(
        str(settings.db_path),
        pattern["case_ids"],
    )

    _case_table(
        db_path=str(
            settings.db_path
        ),
        rows=rows,
        selection_key=(
            "pattern_selected_case_ids"
        ),
        prefix="pattern",
    )
