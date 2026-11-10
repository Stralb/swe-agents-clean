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
    SCANNER_LABELS,
    SCANNER_ORDER,
    latest_scanner_raw,
    scanner_detail,
)


def _bar(
    rows: list[dict[str, Any]],
    *,
    axis_title: str,
    limit: int = 20,
) -> None:
    if not rows:
        st.info("No stored data")
        return

    frame = pd.DataFrame(
        rows[:limit]
    )

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
                title=axis_title,
            ),
            tooltip=[
                alt.Tooltip(
                    "name:N",
                    title="Value",
                ),
                alt.Tooltip(
                    "value:Q",
                    title=axis_title,
                    format=",",
                ),
            ],
        )
        .properties(
            height=300,
        )
    )

    st.altair_chart(
        chart,
        width="stretch",
    )


def _selected_ids() -> set[int]:
    return {
        int(value)
        for value in st.session_state.get(
            "scanner_selected_case_ids",
            [],
        )
    }


def _store_selected(
    values: set[int],
) -> None:
    st.session_state[
        "scanner_selected_case_ids"
    ] = sorted(values)


def render_scanner_insights(
    settings: Any,
) -> None:
    header, back = st.columns(
        [
            5,
            1,
        ]
    )

    header.title(
        "Scanner Insights"
    )

    if back.button(
        "Back",
        width="stretch",
    ):
        st.session_state["nav"] = (
            "Overview"
        )

        st.rerun()

    scanner = str(
        st.session_state.get(
            "selected_scanner"
        )
        or "semgrep"
    )

    scanner = st.selectbox(
        "Scanner",
        list(SCANNER_ORDER),
        index=(
            list(
                SCANNER_ORDER
            ).index(scanner)
            if scanner
            in SCANNER_ORDER
            else 0
        ),
        format_func=lambda value: (
            SCANNER_LABELS.get(
                value,
                value,
            )
        ),
        key="scanner_insight_choice",
    )

    st.session_state[
        "selected_scanner"
    ] = scanner

    details = scanner_detail(
        str(settings.db_path),
        scanner,
    )

    metric = details["metric"]

    metrics = st.columns(6)

    metrics[0].metric(
        "Eligible cases",
        metric["eligible"],
    )

    metrics[1].metric(
        "Terminal coverage",
        (
            f"{metric['terminal']}/"
            f"{metric['eligible']}"
        ),
    )

    metrics[2].metric(
        "Coverage",
        (
            f"{(
                metric['terminal']
                / metric['eligible']
                * 100
                if metric['eligible']
                else 0
            ):.1f}%"
        ),
    )

    metrics[3].metric(
        "Findings",
        metric["findings"],
    )

    metrics[4].metric(
        "Positive cases",
        metric[
            "positive_cases"
        ],
    )

    metrics[5].metric(
        "Errors",
        metric["errors"],
    )

    tabs = st.tabs([
        "Rules and types",
        "Severity",
        "Regions and files",
        "Repositories",
        "Raw evidence",
    ])

    with tabs[0]:
        columns = st.columns(2)

        with columns[0]:
            st.markdown(
                "#### Rules"
            )

            _bar(
                details["rules"],
                axis_title="Findings",
            )

        with columns[1]:
            st.markdown(
                "#### Finding types"
            )

            _bar(
                details["types"],
                axis_title="Findings",
            )

    with tabs[1]:
        _bar(
            details["severities"],
            axis_title="Findings",
        )

    with tabs[2]:
        columns = st.columns(2)

        with columns[0]:
            st.markdown(
                "#### Artifact regions"
            )

            _bar(
                details["regions"],
                axis_title="Findings",
            )

        with columns[1]:
            st.markdown(
                "#### File/path patterns"
            )

            _bar(
                details[
                    "path_patterns"
                ],
                axis_title="Findings",
            )

    with tabs[3]:
        _bar(
            details["repositories"],
            axis_title="Findings",
        )

    with tabs[4]:
        raw_case_ids = [
            int(
                row["case_id"]
            )
            for row in details[
                "case_rows"
            ]
        ]

        if not raw_case_ids:
            st.info(
                "No eligible cases."
            )
        else:
            raw_case = st.selectbox(
                "Case",
                raw_case_ids,
                key=(
                    "scanner_raw_case"
                ),
            )

            raw = latest_scanner_raw(
                str(settings.db_path),
                raw_case,
                scanner,
            )

            if not raw:
                st.info(
                    "No scanner run is "
                    "stored for this case."
                )
            else:
                st.write({
                    "status": raw.get(
                        "status"
                    ),
                    "started_at": raw.get(
                        "started_at"
                    ),
                    "finished_at": raw.get(
                        "finished_at"
                    ),
                })

                stdout = str(
                    raw.get("stdout")
                    or ""
                )

                stderr = str(
                    raw.get("stderr")
                    or ""
                )

                with st.expander(
                    "Structured output",
                    expanded=False,
                ):
                    try:
                        st.json(
                            json.loads(
                                stdout
                            )
                        )
                    except Exception:
                        st.code(stdout)

                if stderr:
                    with st.expander(
                        "Scanner errors",
                        expanded=False,
                    ):
                        st.code(stderr)

    st.subheader(
        "Eligible cases"
    )

    rows = details["case_rows"]
    selected = _selected_ids()

    action_columns = st.columns(
        [
            1,
            1,
            1.2,
            1.2,
            3,
        ]
    )

    if action_columns[0].button(
        "Select all",
        key="scanner-select-all",
    ):
        selected.update(
            int(row["case_id"])
            for row in rows
        )

        _store_selected(
            selected
        )

        st.rerun()

    if action_columns[1].button(
        "Clear",
        key="scanner-clear",
    ):
        selected.clear()

        _store_selected(
            selected
        )

        st.session_state.pop(
            "scanner_prepared_zip",
            None,
        )

        st.rerun()

    if action_columns[2].button(
        "Review selected",
        disabled=not selected,
        key="scanner-review",
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

    if action_columns[3].button(
        "Prepare ZIP",
        disabled=not selected,
        key="scanner-prepare",
    ):
        st.session_state[
            "scanner_prepared_zip"
        ] = selected_evidence_zip(
            Database(
                Path(
                    settings.db_path
                )
            ),
            sorted(selected),
        )

    prepared = st.session_state.get(
        "scanner_prepared_zip"
    )

    if prepared is not None:
        action_columns[4].download_button(
            "Download selected evidence",
            data=prepared,
            file_name=(
                f"{scanner}_cases.zip"
            ),
            mime="application/zip",
            width="stretch",
            key="scanner-download",
        )
    else:
        action_columns[4].markdown(
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
                1.7,
                4,
                1.6,
                0.75,
                0.75,
                0.8,
            ]
        )

        checked = columns[0].checkbox(
            "Select",
            value=(
                case_id in selected
            ),
            key=(
                "scanner-case-"
                f"{scanner}-"
                f"{case_id}"
            ),
            label_visibility=(
                "collapsed"
            ),
        )

        if checked:
            selected.add(case_id)
        else:
            selected.discard(
                case_id
            )

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
                "scanner-inspect-"
                f"{scanner}-"
                f"{case_id}"
            ),
        ):
            st.session_state[
                "selected_case_id"
            ] = case_id

            st.session_state[
                "review_queue_ids"
            ] = [
                int(
                    item["case_id"]
                )
                for item in rows
            ]

            st.session_state["nav"] = (
                "Case Review"
            )

            st.rerun()

    _store_selected(
        selected
    )
