from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

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


PAGE_SIZE = 25

SCANNER_ALIASES = {
    "gitleaks": (
        "gitleaks",
        "secret-ci",
    ),
    "dependency-diff": (
        "dependency-diff",
        "dependency-downgrade",
    ),
    "osv-scanner": (
        "osv",
        "osv-scanner",
        "osv-dependency",
    ),
    "semgrep": (
        "semgrep",
        "semgrep-source",
        "semgrep-script",
    ),
    "trivy": (
        "trivy",
        "trivy-scanner",
        "trivy-dependency",
        "trivy-vuln",
        "trivy-secret",
        "trivy-misconfig",
    ),
    "codeql": (
        "codeql",
    ),
}

SCANNER_JOB_TYPES = {
    "gitleaks": (
        "secret_ci",
    ),
    "dependency-diff": (
        "dependency_downgrade",
    ),
    "osv-scanner": (
        "osv_dependency",
    ),
    "semgrep": (
        "semgrep_source",
        "semgrep_script",
    ),
    "trivy": (
        "trivy_dependency",
        "trivy_vuln",
        "trivy_secret",
        "trivy_misconfig",
    ),
    "codeql": (
        "codeql",
        "codeql_security",
    ),
}

ACTIVE_STATUSES = (
    "pending",
    "queued",
    "claimed",
    "running",
    "processing",
    "active",
    "retrying",
    "created",
)

NOT_APPLICABLE_STATUSES = (
    "not_applicable",
    "not-applicable",
    "skipped",
    "disabled",
)


def _integer(
    value: Any,
) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _scanner_condition(
    column: str,
    scanner: str,
) -> tuple[str, list[Any]]:
    if scanner == "codeql":
        return (
            f"""
            LOWER(
                REPLACE(
                    COALESCE(
                        {column},
                        ''
                    ),
                    '_',
                    '-'
                )
            ) LIKE ?
            """,
            [
                "codeql%",
            ],
        )

    aliases = SCANNER_ALIASES[
        scanner
    ]

    placeholders = ",".join(
        "?"
        for _ in aliases
    )

    return (
        f"""
        LOWER(
            REPLACE(
                COALESCE(
                    {column},
                    ''
                ),
                '_',
                '-'
            )
        ) IN ({placeholders})
        """,
        list(aliases),
    )


def _job_condition(
    scanner: str,
) -> tuple[str, list[Any]]:
    job_types = SCANNER_JOB_TYPES[
        scanner
    ]

    placeholders = ",".join(
        "?"
        for _ in job_types
    )

    return (
        f"job_type IN ({placeholders})",
        list(job_types),
    )


def _error_condition(
    column: str,
) -> str:
    return f"""
    (
        LOWER(
            COALESCE(
                {column},
                ''
            )
        ) LIKE '%error%'

        OR LOWER(
            COALESCE(
                {column},
                ''
            )
        ) LIKE '%fail%'

        OR LOWER(
            COALESCE(
                {column},
                ''
            )
        ) LIKE '%timeout%'

        OR LOWER(
            COALESCE(
                {column},
                ''
            )
        ) LIKE '%blocked%'

        OR LOWER(
            COALESCE(
                {column},
                ''
            )
        ) LIKE '%crash%'
    )
    """


def _status_in(
    column: str,
    values: Iterable[str],
) -> tuple[str, list[Any]]:
    values = tuple(values)

    placeholders = ",".join(
        "?"
        for _ in values
    )

    return (
        f"""
        LOWER(
            COALESCE(
                {column},
                ''
            )
        ) IN ({placeholders})
        """,
        list(values),
    )


def _status_not_in(
    column: str,
    values: Iterable[str],
) -> tuple[str, list[Any]]:
    values = tuple(values)

    placeholders = ",".join(
        "?"
        for _ in values
    )

    return (
        f"""
        LOWER(
            COALESCE(
                {column},
                ''
            )
        ) NOT IN ({placeholders})
        """,
        list(values),
    )


def _candidate_cte(
    scanner: str,
    view: str,
) -> tuple[str, list[Any]]:
    finding_condition, finding_params = (
        _scanner_condition(
            "scanner",
            scanner,
        )
    )

    run_condition, run_params = (
        _scanner_condition(
            "scanner",
            scanner,
        )
    )

    job_condition, job_params = (
        _job_condition(scanner)
    )

    active_job_condition, active_job_params = (
        _status_in(
            "status",
            ACTIVE_STATUSES,
        )
    )

    active_run_condition, active_run_params = (
        _status_in(
            "status",
            ACTIVE_STATUSES,
        )
    )

    applicable_job_condition, applicable_job_params = (
        _status_not_in(
            "status",
            NOT_APPLICABLE_STATUSES,
        )
    )

    applicable_run_condition, applicable_run_params = (
        _status_not_in(
            "status",
            NOT_APPLICABLE_STATUSES,
        )
    )

    findings_sql = f"""
        SELECT DISTINCT
            case_id
        FROM scanner_findings
        WHERE {finding_condition}
          AND case_id IS NOT NULL
    """

    findings_parameters = list(
        finding_params
    )

    errors_sql = f"""
        SELECT DISTINCT
            case_id
        FROM scanner_jobs
        WHERE {job_condition}
          AND {_error_condition("status")}
          AND case_id IS NOT NULL

        UNION

        SELECT DISTINCT
            case_id
        FROM scanner_runs
        WHERE {run_condition}
          AND {_error_condition("status")}
          AND case_id IS NOT NULL
    """

    errors_parameters = [
        *job_params,
        *run_params,
    ]

    active_sql = f"""
        SELECT DISTINCT
            case_id
        FROM scanner_jobs
        WHERE {job_condition}
          AND {active_job_condition}
          AND case_id IS NOT NULL

        UNION

        SELECT DISTINCT
            case_id
        FROM scanner_runs
        WHERE {run_condition}
          AND {active_run_condition}
          AND case_id IS NOT NULL
    """

    active_parameters = [
        *job_params,
        *active_job_params,
        *run_params,
        *active_run_params,
    ]

    applicable_sql = f"""
        SELECT DISTINCT
            case_id
        FROM scanner_jobs
        WHERE {job_condition}
          AND {applicable_job_condition}
          AND case_id IS NOT NULL

        UNION

        SELECT DISTINCT
            case_id
        FROM scanner_runs
        WHERE {run_condition}
          AND {applicable_run_condition}
          AND case_id IS NOT NULL
    """

    applicable_parameters = [
        *job_params,
        *applicable_job_params,
        *run_params,
        *applicable_run_params,
    ]

    if view == "Findings":
        body = findings_sql
        parameters = findings_parameters

    elif view == "Errors":
        body = errors_sql
        parameters = errors_parameters

    elif view == "In progress":
        body = active_sql
        parameters = active_parameters

    elif view == "All applicable":
        body = applicable_sql
        parameters = applicable_parameters

    else:
        body = (
            findings_sql
            + "\nUNION\n"
            + errors_sql
        )

        parameters = [
            *findings_parameters,
            *errors_parameters,
        ]

    return (
        f"""
        WITH candidate_ids AS (
            SELECT DISTINCT
                case_id
            FROM (
                {body}
            )
            WHERE case_id IS NOT NULL
        )
        """,
        parameters,
    )


def _search_sql(
    search: str,
) -> tuple[str, list[Any]]:
    search = search.strip()

    if not search:
        return "", []

    value = (
        "%"
        + search.lower()
        + "%"
    )

    return (
        """
        WHERE (
            LOWER(
                CAST(c.id AS TEXT)
            ) LIKE ?

            OR LOWER(
                COALESCE(
                    r.full_name,
                    ''
                )
            ) LIKE ?

            OR LOWER(
                COALESCE(
                    i.title,
                    ''
                )
            ) LIKE ?
        )
        """,
        [
            value,
            value,
            value,
        ],
    )


def _candidate_count(
    db: Database,
    scanner: str,
    view: str,
    search: str = "",
) -> int:
    candidate_cte, candidate_params = (
        _candidate_cte(
            scanner,
            view,
        )
    )

    search_clause, search_params = (
        _search_sql(search)
    )

    row = db.one(
        f"""
        {candidate_cte}

        SELECT
            COUNT(*) AS n

        FROM candidate_ids selected

        JOIN cases c
          ON c.id=selected.case_id

        JOIN repos r
          ON r.id=c.repo_id

        JOIN issues i
          ON i.id=c.issue_id

        {search_clause}
        """,
        tuple([
            *candidate_params,
            *search_params,
        ]),
    ) or {}

    return _integer(
        row.get("n")
    )


def _scanner_case_page(
    db: Database,
    *,
    scanner: str,
    view: str,
    search: str,
    page: int,
) -> tuple[
    int,
    list[dict[str, Any]],
]:
    candidate_cte, candidate_params = (
        _candidate_cte(
            scanner,
            view,
        )
    )

    finding_condition, finding_params = (
        _scanner_condition(
            "scanner",
            scanner,
        )
    )

    search_clause, search_params = (
        _search_sql(search)
    )

    total = _candidate_count(
        db,
        scanner,
        view,
        search,
    )

    page = max(
        1,
        int(page),
    )

    offset = (
        page - 1
    ) * PAGE_SIZE

    rows = db.query(
        f"""
        {candidate_cte},

        scanner_findings_for_case AS (
            SELECT
                case_id,
                COUNT(*) AS finding_count,

                SUM(
                    CASE
                        WHEN COALESCE(
                            introduced,
                            0
                        )=1
                        THEN 1
                        ELSE 0
                    END
                ) AS introduced_count

            FROM scanner_findings

            WHERE {finding_condition}

            GROUP BY case_id
        )

        SELECT
            c.id AS case_id,
            r.full_name AS repository,

            SUBSTR(
                COALESCE(
                    i.title,
                    ''
                ),
                1,
                120
            ) AS issue_title,

            c.status,
            c.final_label,

            COALESCE(
                findings.finding_count,
                0
            ) AS finding_count,

            COALESCE(
                findings.introduced_count,
                0
            ) AS introduced_count

        FROM candidate_ids selected

        JOIN cases c
          ON c.id=selected.case_id

        JOIN repos r
          ON r.id=c.repo_id

        JOIN issues i
          ON i.id=c.issue_id

        LEFT JOIN scanner_findings_for_case findings
          ON findings.case_id=c.id

        {search_clause}

        ORDER BY
            introduced_count DESC,
            finding_count DESC,
            c.updated_at DESC,
            c.id DESC

        LIMIT ?
        OFFSET ?
        """,
        tuple([
            *candidate_params,
            *finding_params,
            *search_params,
            PAGE_SIZE,
            offset,
        ]),
    )

    return total, rows


def _scanner_metrics(
    db: Database,
    scanner: str,
) -> dict[str, int]:
    applicable = _candidate_count(
        db,
        scanner,
        "All applicable",
    )

    active = _candidate_count(
        db,
        scanner,
        "In progress",
    )

    errors = _candidate_count(
        db,
        scanner,
        "Errors",
    )

    finding_condition, finding_params = (
        _scanner_condition(
            "scanner",
            scanner,
        )
    )

    finding_row = db.one(
        f"""
        SELECT
            COUNT(*) AS findings,

            COUNT(
                DISTINCT case_id
            ) AS finding_cases,

            COUNT(
                DISTINCT CASE
                    WHEN COALESCE(
                        introduced,
                        0
                    )=1
                    THEN case_id
                END
            ) AS positive_cases

        FROM scanner_findings

        WHERE {finding_condition}
        """,
        tuple(finding_params),
    ) or {}

    return {
        "applicable": applicable,
        "completed": max(
            0,
            applicable - active,
        ),
        "active": active,
        "errors": errors,
        "findings": _integer(
            finding_row.get(
                "findings"
            )
        ),
        "finding_cases": _integer(
            finding_row.get(
                "finding_cases"
            )
        ),
        "positive_cases": _integer(
            finding_row.get(
                "positive_cases"
            )
        ),
    }


def _bar(
    rows: list[dict[str, Any]],
    *,
    category: str,
    value: str,
    title: str,
) -> None:
    if not rows:
        st.info(
            "No stored finding data "
            "for this view."
        )
        return

    frame = pd.DataFrame(
        rows[:20]
    )

    chart = (
        alt.Chart(frame)
        .mark_bar(
            cornerRadiusEnd=5,
        )
        .encode(
            y=alt.Y(
                f"{category}:N",
                sort="-x",
                title=None,
            ),
            x=alt.X(
                f"{value}:Q",
                title="Findings",
            ),
            tooltip=[
                alt.Tooltip(
                    f"{category}:N",
                    title=title,
                ),
                alt.Tooltip(
                    f"{value}:Q",
                    title="Findings",
                    format=",",
                ),
            ],
        )
        .properties(
            height=min(
                380,
                max(
                    180,
                    len(frame) * 25,
                ),
            )
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
        key="scanner-back",
    ):
        st.session_state["nav"] = (
            "Overview"
        )

        st.rerun()

    previous_scanner = str(
        st.session_state.get(
            "selected_scanner"
        )
        or "codeql"
    )

    scanner = st.selectbox(
        "Scanner",
        list(SCANNER_ORDER),
        index=(
            list(
                SCANNER_ORDER
            ).index(
                previous_scanner
            )
            if previous_scanner
            in SCANNER_ORDER
            else 0
        ),
        format_func=lambda value: (
            SCANNER_LABELS.get(
                value,
                value,
            )
        ),
        key="scanner-insight-choice",
    )

    if scanner != previous_scanner:
        st.session_state[
            "scanner_page"
        ] = 1

        st.session_state.pop(
            "scanner_case_search",
            None,
        )

        st.session_state[
            "scanner_selected_case_ids"
        ] = []

        st.session_state.pop(
            "scanner_prepared_zip",
            None,
        )

    st.session_state[
        "selected_scanner"
    ] = scanner

    db = Database(
        Path(settings.db_path)
    )

    metrics = _scanner_metrics(
        db,
        scanner,
    )

    metric_columns = st.columns(6)

    metric_columns[0].metric(
        "Applicable",
        metrics["applicable"],
        help=(
            "Cases not marked "
            "not_applicable for this scanner."
        ),
    )

    metric_columns[1].metric(
        "Completed",
        (
            f"{metrics['completed']}/"
            f"{metrics['applicable']}"
        ),
    )

    metric_columns[2].metric(
        "In progress",
        metrics["active"],
    )

    metric_columns[3].metric(
        "Findings",
        metrics["findings"],
    )

    metric_columns[4].metric(
        "Positive cases",
        metrics["positive_cases"],
    )

    metric_columns[5].metric(
        "Errors",
        metrics["errors"],
    )

    # This loads finding aggregations only.
    # scanner_detail no longer materialises
    # every applicable case.
    details = scanner_detail(
        str(settings.db_path),
        scanner,
    )

    chart_tabs = []

    for label, key in (
        (
            "Rules",
            "rules",
        ),
        (
            "Finding types",
            "types",
        ),
        (
            "Severity",
            "severities",
        ),
        (
            "Regions",
            "regions",
        ),
        (
            "File patterns",
            "path_patterns",
        ),
        (
            "Repositories",
            "repositories",
        ),
    ):
        values = details.get(
            key,
            [],
        )

        if values:
            chart_tabs.append(
                (
                    label,
                    key,
                    values,
                )
            )

    if chart_tabs:
        tabs = st.tabs(
            [
                label
                for label, _key, _values
                in chart_tabs
            ]
        )

        for tab, (
            label,
            _key,
            values,
        ) in zip(
            tabs,
            chart_tabs,
        ):
            with tab:
                _bar(
                    values,
                    category="name",
                    value="value",
                    title=label,
                )

    elif metrics["completed"] > 0:
        st.success(
            (
                f"{metrics['completed']} "
                "applicable cases completed "
                "without persisted findings."
            )
        )
    else:
        st.info(
            "No completed scanner evidence "
            "is available yet."
        )

    st.markdown(
        "### Cases"
    )

    view = st.selectbox(
        "Case set",
        [
            "Findings & errors",
            "Findings",
            "Errors",
            "In progress",
            "All applicable",
        ],
        index=0,
        key=(
            "scanner-case-view-"
            + scanner
        ),
        help=(
            "The default loads only cases "
            "with findings or errors. "
            "All applicable remains available "
            "but is paginated."
        ),
    )

    search = st.text_input(
        "Search cases",
        placeholder=(
            "Case ID, repository or issue title"
        ),
        key="scanner_case_search",
    )

    signature = repr(
        (
            scanner,
            view,
            search,
        )
    )

    if (
        st.session_state.get(
            "scanner_case_signature"
        )
        != signature
    ):
        st.session_state[
            "scanner_case_signature"
        ] = signature

        st.session_state[
            "scanner_page"
        ] = 1

    page = max(
        1,
        int(
            st.session_state.get(
                "scanner_page",
                1,
            )
        ),
    )

    total, rows = _scanner_case_page(
        db,
        scanner=scanner,
        view=view,
        search=search,
        page=page,
    )

    total_pages = max(
        1,
        math.ceil(
            total / PAGE_SIZE
        ),
    )

    page = min(
        page,
        total_pages,
    )

    st.session_state[
        "scanner_page"
    ] = page

    page_ids = [
        int(row["case_id"])
        for row in rows
    ]

    start_row = (
        (page - 1)
        * PAGE_SIZE
        + 1
        if total
        else 0
    )

    end_row = min(
        total,
        page * PAGE_SIZE,
    )

    st.caption(
        (
            f"{start_row}–{end_row} "
            f"of {total} matching cases · "
            f"{PAGE_SIZE} per page"
        )
    )

    selected = _selected_ids()

    toolbar = st.columns(
        [
            1,
            1,
            1.2,
            1.2,
            3,
        ]
    )

    if toolbar[0].button(
        "Select page",
        key="scanner-select-page",
    ):
        selected.update(
            page_ids
        )

        _store_selected(
            selected
        )

        st.rerun()

    if toolbar[1].button(
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

    if toolbar[2].button(
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

    if toolbar[3].button(
        "Prepare ZIP",
        disabled=not selected,
        key="scanner-prepare",
    ):
        st.session_state[
            "scanner_prepared_zip"
        ] = selected_evidence_zip(
            db,
            sorted(selected),
        )

    prepared = st.session_state.get(
        "scanner_prepared_zip"
    )

    if prepared is not None:
        toolbar[4].download_button(
            "Download selected evidence",
            data=prepared,
            file_name=(
                f"{scanner}_selected_cases.zip"
            ),
            mime="application/zip",
            width="stretch",
            key="scanner-download",
        )
    else:
        toolbar[4].markdown(
            f"**{len(selected)} selected**"
        )

    if not rows:
        st.info(
            "No cases match this scanner view."
        )

    for row in rows:
        case_id = int(
            row["case_id"]
        )

        columns = st.columns(
            [
                0.42,
                0.62,
                1.8,
                4.4,
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
                "scanner-case-"
                f"{scanner}-"
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

        columns[4].metric(
            "Findings",
            _integer(
                row.get(
                    "finding_count"
                )
            ),
        )

        columns[5].metric(
            "Introduced",
            _integer(
                row.get(
                    "introduced_count"
                )
            ),
        )

        if columns[6].button(
            "Inspect",
            key=(
                "scanner-inspect-"
                f"{scanner}-"
                f"{case_id}"
            ),
            width="stretch",
        ):
            st.session_state[
                "selected_case_id"
            ] = case_id

            st.session_state[
                "review_queue_ids"
            ] = page_ids

            st.session_state["nav"] = (
                "Case Review"
            )

            st.rerun()

    _store_selected(selected)

    previous, centre, next_page = (
        st.columns(
            [
                1,
                3,
                1,
            ]
        )
    )

    if previous.button(
        "Previous",
        disabled=page <= 1,
        key="scanner-previous",
        width="stretch",
    ):
        st.session_state[
            "scanner_page"
        ] = page - 1

        st.rerun()

    centre.markdown(
        (
            "<div style='text-align:center;"
            "padding-top:.42rem'>"
            f"<strong>Page {page} "
            f"of {total_pages}</strong>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    if next_page.button(
        "Next",
        disabled=(
            page >= total_pages
        ),
        key="scanner-next",
        width="stretch",
    ):
        st.session_state[
            "scanner_page"
        ] = page + 1

        st.rerun()

    if page_ids:
        with st.expander(
            "Raw scanner evidence",
            expanded=False,
        ):
            raw_case = st.selectbox(
                "Case",
                page_ids,
                key=(
                    "scanner-raw-case-"
                    + scanner
                ),
            )

            raw = latest_scanner_raw(
                str(settings.db_path),
                raw_case,
                scanner,
            )

            if not raw:
                st.info(
                    "No stored run payload "
                    "for this case."
                )
            else:
                st.write({
                    "status":
                        raw.get("status"),
                    "started_at":
                        raw.get(
                            "started_at"
                        ),
                    "finished_at":
                        raw.get(
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

                if stdout:
                    try:
                        st.json(
                            json.loads(stdout)
                        )
                    except Exception:
                        st.code(stdout)

                if stderr:
                    st.code(stderr)
