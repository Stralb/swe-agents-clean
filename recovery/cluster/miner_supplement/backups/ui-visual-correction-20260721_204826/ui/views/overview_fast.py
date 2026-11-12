from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import streamlit as st

from src.db.database import Database


PAGE_SIZE = 40

POOL_LABELS = {
    "mining": "Mining",
    "cheap_analysis": "Cheap",
    "codeql_security": "CodeQL",
}


STAGE_SQL = """
CASE
    WHEN c.status = 'reviewed'
      OR COALESCE(
            TRIM(c.final_label),
            ''
         ) <> ''
    THEN 'Reviewed'

    WHEN c.status = 'needs_review'
    THEN 'Needs review'

    WHEN c.status = 'scanned_clean'
    THEN 'Clean'

    WHEN c.status IN (
        'scanner_running',
        'metadata_collected'
    )
    THEN 'Scanning'

    WHEN c.status IN (
        'scan_blocked',
        'scanner_blocked'
    )
    THEN 'Blocked'

    ELSE 'Validated'
END
"""


def _safe_one(
    db: Database,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> dict[str, Any]:
    try:
        return db.one(
            query,
            parameters,
        ) or {}
    except Exception:
        return {}


def _safe_query(
    db: Database,
    query: str,
    parameters: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    try:
        return db.query(
            query,
            parameters,
        )
    except Exception:
        return []


def _integer(
    value: Any,
) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _read_json(
    path: Path,
) -> dict[str, Any]:
    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(payload, dict):
            return payload

    except Exception:
        pass

    return {}


def _summary(
    db: Database,
) -> dict[str, int]:
    cases = _safe_one(
        db,
        """
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status = 'needs_review'
                    THEN 1
                    ELSE 0
                END
            ) AS needs_review,

            SUM(
                CASE
                    WHEN status IN (
                        'metadata_collected',
                        'validated',
                        'scanner_running',
                        'scan_blocked',
                        'scanner_blocked'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS in_progress,

            SUM(
                CASE
                    WHEN status = 'scanned_clean'
                    THEN 1
                    ELSE 0
                END
            ) AS clean,

            SUM(
                CASE
                    WHEN status = 'reviewed'
                      OR COALESCE(
                            TRIM(final_label),
                            ''
                         ) <> ''
                    THEN 1
                    ELSE 0
                END
            ) AS reviewed
        FROM cases
        """,
    )

    findings = _safe_one(
        db,
        """
        SELECT
            COUNT(*) AS findings,

            SUM(
                CASE
                    WHEN COALESCE(
                        introduced,
                        0
                    ) = 1
                    THEN 1
                    ELSE 0
                END
            ) AS introduced
        FROM scanner_findings
        """,
    )

    failures = _safe_one(
        db,
        """
        SELECT
            COUNT(*) AS failed
        FROM scanner_jobs
        WHERE LOWER(
            COALESCE(status, '')
        ) IN (
            'failed',
            'error'
        )
        """,
    )

    return {
        "total": _integer(
            cases.get("total")
        ),
        "needs_review": _integer(
            cases.get("needs_review")
        ),
        "in_progress": _integer(
            cases.get("in_progress")
        ),
        "clean": _integer(
            cases.get("clean")
        ),
        "reviewed": _integer(
            cases.get("reviewed")
        ),
        "introduced": _integer(
            findings.get("introduced")
        ),
        "failed_jobs": _integer(
            failures.get("failed")
        ),
    }


def _scan_progress(
    db: Database,
) -> dict[str, dict[str, int]]:
    rows = _safe_query(
        db,
        """
        SELECT
            job_type,

            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN LOWER(
                        COALESCE(status, '')
                    ) IN (
                        'done',
                        'complete',
                        'completed',
                        'success',
                        'succeeded'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS finished,

            SUM(
                CASE
                    WHEN LOWER(
                        COALESCE(status, '')
                    ) IN (
                        'claimed',
                        'running',
                        'processing',
                        'active'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS active,

            SUM(
                CASE
                    WHEN LOWER(
                        COALESCE(status, '')
                    ) = 'pending'
                    THEN 1
                    ELSE 0
                END
            ) AS pending,

            SUM(
                CASE
                    WHEN LOWER(
                        COALESCE(status, '')
                    ) IN (
                        'failed',
                        'error'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS failed

        FROM scanner_jobs

        WHERE job_type IN (
            'cheap_analysis',
            'codeql_security'
        )

        GROUP BY job_type
        """,
    )

    result: dict[
        str,
        dict[str, int]
    ] = {}

    for row in rows:
        job_type = str(
            row.get("job_type")
            or ""
        )

        result[job_type] = {
            "total": _integer(
                row.get("total")
            ),
            "finished": _integer(
                row.get("finished")
            ),
            "active": _integer(
                row.get("active")
            ),
            "pending": _integer(
                row.get("pending")
            ),
            "failed": _integer(
                row.get("failed")
            ),
        }

    return result


def load_live_bundle(
    db_path: str,
    spool_root: str,
) -> dict[str, Any]:
    db = Database(
        Path(db_path)
    )

    runtime = _read_json(
        Path(spool_root)
        / "status"
        / "autoscaler.json"
    )

    return {
        "summary": _summary(db),
        "progress": _scan_progress(db),
        "runtime": runtime,
        "loaded_at": time.time(),
    }


def _distinct_values(
    db: Database,
    query: str,
) -> list[str]:
    rows = _safe_query(
        db,
        query,
    )

    values: list[str] = []

    for row in rows:
        value = str(
            row.get("value")
            or ""
        ).strip()

        if (
            value
            and value not in values
        ):
            values.append(value)

    return values


def filter_options(
    db_path: str,
) -> dict[str, list[str]]:
    db = Database(
        Path(db_path)
    )

    return {
        "signals": _distinct_values(
            db,
            """
            SELECT DISTINCT
                COALESCE(
                    NULLIF(
                        downstream_signal,
                        ''
                    ),
                    'pending'
                ) AS value
            FROM cases
            ORDER BY value
            """,
        ),
        "labels": _distinct_values(
            db,
            """
            SELECT DISTINCT
                final_label AS value
            FROM cases
            WHERE COALESCE(
                TRIM(final_label),
                ''
            ) <> ''
            ORDER BY value
            """,
        ),
        "repositories": _distinct_values(
            db,
            """
            SELECT
                full_name AS value
            FROM repos
            ORDER BY full_name
            """,
        ),
    }


def fetch_case_page(
    db_path: str,
    *,
    search: str,
    stage: str,
    signal: str,
    label: str,
    repository: str,
    sort: str,
    page: int,
) -> tuple[
    int,
    list[dict[str, Any]],
]:
    db = Database(
        Path(db_path)
    )

    conditions: list[str] = []
    parameters: list[Any] = []

    search = search.strip()

    if search:
        search_value = (
            "%"
            + search.lower()
            + "%"
        )

        conditions.append(
            """
            (
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
            """
        )

        parameters.extend(
            [
                search_value,
                search_value,
                search_value,
            ]
        )

    if stage != "All":
        conditions.append(
            f"({STAGE_SQL}) = ?"
        )
        parameters.append(stage)

    if signal != "All":
        conditions.append(
            """
            LOWER(
                COALESCE(
                    NULLIF(
                        c.downstream_signal,
                        ''
                    ),
                    'pending'
                )
            ) = LOWER(?)
            """
        )
        parameters.append(signal)

    if label == "Unreviewed":
        conditions.append(
            """
            COALESCE(
                TRIM(c.final_label),
                ''
            ) = ''
            """
        )

    elif label != "All":
        conditions.append(
            """
            COALESCE(
                c.final_label,
                ''
            ) = ?
            """
        )
        parameters.append(label)

    if repository != "All":
        conditions.append(
            "r.full_name = ?"
        )
        parameters.append(repository)

    where_sql = (
        "WHERE "
        + " AND ".join(
            conditions
        )
        if conditions
        else ""
    )

    count_query = f"""
        SELECT
            COUNT(*) AS n

        FROM cases c

        JOIN repos r
          ON r.id = c.repo_id

        JOIN issues i
          ON i.id = c.issue_id

        {where_sql}
    """

    count_row = _safe_one(
        db,
        count_query,
        tuple(parameters),
    )

    total = _integer(
        count_row.get("n")
    )

    order_options = {
        "Priority": f"""
            CASE ({STAGE_SQL})
                WHEN 'Needs review' THEN 0
                WHEN 'Blocked' THEN 1
                WHEN 'Scanning' THEN 2
                WHEN 'Validated' THEN 3
                WHEN 'Clean' THEN 4
                WHEN 'Reviewed' THEN 5
                ELSE 6
            END,

            COALESCE(
                finding_counts.finding_count,
                0
            ) DESC,

            c.updated_at DESC,
            c.id DESC
        """,

        "Newest": """
            c.updated_at DESC,
            c.id DESC
        """,

        "Oldest": """
            c.updated_at ASC,
            c.id ASC
        """,

        "Repository": """
            r.full_name ASC,
            c.id DESC
        """,

        "Case ID": """
            c.id ASC
        """,
    }

    order_sql = order_options.get(
        sort,
        order_options["Priority"],
    )

    page = max(
        1,
        int(page),
    )

    offset = (
        page - 1
    ) * PAGE_SIZE

    page_query = f"""
        WITH finding_counts AS (
            SELECT
                case_id,
                COUNT(*) AS finding_count
            FROM scanner_findings
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
                115
            ) AS issue_title,

            ({STAGE_SQL}) AS stage,

            COALESCE(
                NULLIF(
                    c.downstream_signal,
                    ''
                ),
                'pending'
            ) AS signal,

            COALESCE(
                NULLIF(
                    c.final_label,
                    ''
                ),
                'Unreviewed'
            ) AS label,

            COALESCE(
                finding_counts.finding_count,
                0
            ) AS finding_count,

            c.updated_at

        FROM cases c

        JOIN repos r
          ON r.id = c.repo_id

        JOIN issues i
          ON i.id = c.issue_id

        LEFT JOIN finding_counts
          ON finding_counts.case_id = c.id

        {where_sql}

        ORDER BY
            {order_sql}

        LIMIT ?
        OFFSET ?
    """

    page_parameters = list(
        parameters
    )

    page_parameters.extend(
        [
            PAGE_SIZE,
            offset,
        ]
    )

    rows = _safe_query(
        db,
        page_query,
        tuple(page_parameters),
    )

    return total, rows


def _render_summary(
    summary: dict[str, int],
) -> None:
    metrics = (
        (
            "Cases",
            summary["total"],
        ),
        (
            "Needs review",
            summary["needs_review"],
        ),
        (
            "In progress",
            summary["in_progress"],
        ),
        (
            "Clean",
            summary["clean"],
        ),
        (
            "Reviewed",
            summary["reviewed"],
        ),
        (
            "Introduced findings",
            summary["introduced"],
        ),
    )

    columns = st.columns(
        len(metrics)
    )

    for column, (
        label,
        value,
    ) in zip(
        columns,
        metrics,
    ):
        column.metric(
            label,
            value,
        )

    if summary["failed_jobs"] > 0:
        st.warning(
            f"{summary['failed_jobs']} scanner "
            "job(s) currently have a failed state."
        )


def _render_runtime(
    runtime: dict[str, Any],
) -> None:
    pools = runtime.get(
        "pools",
        {},
    )

    if not isinstance(
        pools,
        dict,
    ) or not pools:
        st.info(
            "Runtime status is not available yet."
        )
        return

    allocation = runtime.get(
        "allocation",
        {},
    )

    if not isinstance(
        allocation,
        dict,
    ):
        allocation = {}

    columns = st.columns(
        [
            1.3,
            1.3,
            1.3,
            2.2,
        ]
    )

    for column, pool in zip(
        columns[:3],
        (
            "mining",
            "cheap_analysis",
            "codeql_security",
        ),
    ):
        details = pools.get(
            pool,
            {},
        )

        if not isinstance(
            details,
            dict,
        ):
            details = {}

        counts = details.get(
            "counts",
            {},
        )

        if not isinstance(
            counts,
            dict,
        ):
            counts = {}

        active = _integer(
            details.get(
                "active_workers"
            )
        )

        desired = _integer(
            details.get(
                "desired_workers"
            )
        )

        backlog = (
            _integer(
                counts.get("pending")
            )
            + _integer(
                counts.get("claimed")
            )
        )

        column.metric(
            POOL_LABELS[pool],
            f"{active}/{desired}",
            delta=(
                f"{backlog} queued"
            ),
            delta_color="off",
        )

    worker_budget = _integer(
        allocation.get(
            "worker_budget"
        )
    )

    allocated = _integer(
        allocation.get(
            "allocated_workers"
        )
    )

    mode = str(
        allocation.get("mode")
        or "unknown"
    ).title()

    columns[3].metric(
        "Scheduler",
        mode,
        delta=(
            f"{allocated}/{worker_budget} "
            "workers allocated"
        ),
        delta_color="off",
    )


def _render_progress(
    progress: dict[
        str,
        dict[str, int],
    ],
) -> None:
    for job_type, label in (
        (
            "cheap_analysis",
            "Cheap analysis",
        ),
        (
            "codeql_security",
            "CodeQL",
        ),
    ):
        details = progress.get(
            job_type,
            {},
        )

        total = _integer(
            details.get("total")
        )

        finished = _integer(
            details.get("finished")
        )

        active = _integer(
            details.get("active")
        )

        pending = _integer(
            details.get("pending")
        )

        failed = _integer(
            details.get("failed")
        )

        ratio = (
            finished / total
            if total > 0
            else 0.0
        )

        st.progress(
            min(
                1.0,
                max(
                    0.0,
                    ratio,
                ),
            ),
            text=(
                f"{label}: {finished}/{total} "
                f"finished · {active} active · "
                f"{pending} pending · "
                f"{failed} failed"
            ),
        )


def _render_live_status(
    db_path: str,
    spool_root: str,
) -> None:
    payload = load_live_bundle(
        db_path,
        spool_root,
    )

    _render_summary(
        payload["summary"]
    )

    st.markdown(
        "### Pipeline"
    )

    _render_runtime(
        payload["runtime"]
    )

    st.markdown(
        "### Processing progress"
    )

    _render_progress(
        payload["progress"]
    )

    st.caption(
        "Live values refreshed at "
        + time.strftime(
            "%H:%M:%S",
            time.localtime(
                payload["loaded_at"]
            ),
        )
        + " · refresh interval: 3 seconds"
    )


def _open_case(
    case_id: int,
    queue_ids: list[int],
) -> None:
    st.session_state[
        "selected_case_id"
    ] = int(case_id)

    st.session_state[
        "review_queue_ids"
    ] = [
        int(value)
        for value in queue_ids
    ]

    st.session_state[
        "nav"
    ] = "Case Review"

    st.rerun()


def _render_case_rows(
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        st.info(
            "No cases match the current filters."
        )
        return

    page_ids = [
        _integer(
            row.get("case_id")
        )
        for row in rows
    ]

    header = st.columns(
        [
            0.55,
            1.7,
            4.0,
            1.1,
            1.1,
            1.6,
            0.75,
            0.85,
        ]
    )

    labels = (
        "Case",
        "Repository",
        "Issue",
        "Stage",
        "Signal",
        "Label",
        "Findings",
        "",
    )

    for column, label in zip(
        header,
        labels,
    ):
        column.markdown(
            f"**{label}**"
        )

    for row in rows:
        case_id = _integer(
            row.get("case_id")
        )

        with st.container(
            border=True
        ):
            columns = st.columns(
                [
                    0.55,
                    1.7,
                    4.0,
                    1.1,
                    1.1,
                    1.6,
                    0.75,
                    0.85,
                ]
            )

            columns[0].markdown(
                f"**#{case_id}**"
            )

            columns[1].write(
                str(
                    row.get("repository")
                    or ""
                )
            )

            columns[2].write(
                str(
                    row.get("issue_title")
                    or "Untitled issue"
                )
            )

            columns[3].write(
                str(
                    row.get("stage")
                    or ""
                )
            )

            columns[4].write(
                str(
                    row.get("signal")
                    or "pending"
                )
            )

            columns[5].write(
                str(
                    row.get("label")
                    or "Unreviewed"
                )
            )

            columns[6].write(
                _integer(
                    row.get(
                        "finding_count"
                    )
                )
            )

            if columns[7].button(
                "Inspect",
                key=(
                    f"overview-inspect-"
                    f"{case_id}"
                ),
                width="stretch",
            ):
                _open_case(
                    case_id,
                    page_ids,
                )


def _render_live_cases(
    db_path: str,
    search: str,
    stage: str,
    signal: str,
    label: str,
    repository: str,
    sort: str,
) -> None:
    page = _integer(
        st.session_state.get(
            "overview_page",
            1,
        )
    )

    page = max(
        1,
        page,
    )

    total, rows = fetch_case_page(
        db_path,
        search=search,
        stage=stage,
        signal=signal,
        label=label,
        repository=repository,
        sort=sort,
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
        "overview_page"
    ] = page

    first_row = (
        ((page - 1) * PAGE_SIZE) + 1
        if total > 0
        else 0
    )

    last_row = min(
        total,
        page * PAGE_SIZE,
    )

    st.markdown(
        f"**{total} matching cases** · "
        f"showing {first_row}–{last_row}"
    )

    _render_case_rows(rows)

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
        disabled=(
            page <= 1
        ),
        width="stretch",
        key="overview-previous-page",
    ):
        st.session_state[
            "overview_page"
        ] = max(
            1,
            page - 1,
        )

        st.rerun()

    centre.markdown(
        "<div style='text-align:center;"
        "padding-top:0.45rem'>"
        f"<strong>Page {page} of "
        f"{total_pages}</strong>"
        "</div>",
        unsafe_allow_html=True,
    )

    if next_page.button(
        "Next",
        disabled=(
            page >= total_pages
        ),
        width="stretch",
        key="overview-next-page",
    ):
        st.session_state[
            "overview_page"
        ] = min(
            total_pages,
            page + 1,
        )

        st.rerun()

    st.caption(
        "Visible cases refreshed at "
        + time.strftime("%H:%M:%S")
        + " · page, filters and search preserved"
    )


if hasattr(
    st,
    "fragment",
):
    @st.fragment(
        run_every="3s"
    )
    def _live_status_fragment(
        db_path: str,
        spool_root: str,
    ) -> None:
        _render_live_status(
            db_path,
            spool_root,
        )


    @st.fragment(
        run_every="3s"
    )
    def _live_cases_fragment(
        db_path: str,
        search: str,
        stage: str,
        signal: str,
        label: str,
        repository: str,
        sort: str,
    ) -> None:
        _render_live_cases(
            db_path,
            search,
            stage,
            signal,
            label,
            repository,
            sort,
        )

else:
    def _live_status_fragment(
        db_path: str,
        spool_root: str,
    ) -> None:
        _render_live_status(
            db_path,
            spool_root,
        )


    def _live_cases_fragment(
        db_path: str,
        search: str,
        stage: str,
        signal: str,
        label: str,
        repository: str,
        sort: str,
    ) -> None:
        _render_live_cases(
            db_path,
            search,
            stage,
            signal,
            label,
            repository,
            sort,
        )


def render_overview_fast(
    settings: Any,
) -> None:
    title_column, runtime_column = (
        st.columns(
            [
                5,
                1.25,
            ]
        )
    )

    title_column.title(
        "Overview"
    )

    title_column.caption(
        "Live operational dashboard. "
        "Only the live sections refresh; "
        "navigation and controls remain intact."
    )

    if runtime_column.button(
        "Runtime controls",
        width="stretch",
        key="overview-runtime-controls",
    ):
        st.session_state[
            "nav"
        ] = "Runtime"

        st.rerun()

    _live_status_fragment(
        str(settings.db_path),
        "data/distributed_spool",
    )

    st.markdown(
        "### Cases"
    )

    options = filter_options(
        str(settings.db_path)
    )

    search_column, sort_column = (
        st.columns(
            [
                4,
                1.35,
            ]
        )
    )

    search = search_column.text_input(
        "Search cases",
        placeholder=(
            "Case ID, repository or issue title"
        ),
        key="overview_search",
    )

    sort = sort_column.selectbox(
        "Sort",
        [
            "Priority",
            "Newest",
            "Oldest",
            "Repository",
            "Case ID",
        ],
        key="overview_sort",
    )

    filters = st.columns(4)

    stage = filters[0].selectbox(
        "Stage",
        [
            "All",
            "Needs review",
            "Blocked",
            "Scanning",
            "Validated",
            "Clean",
            "Reviewed",
        ],
        key="overview_stage",
    )

    signal = filters[1].selectbox(
        "Signal",
        [
            "All",
            *options["signals"],
        ],
        key="overview_signal",
    )

    label = filters[2].selectbox(
        "Label",
        [
            "All",
            "Unreviewed",
            *options["labels"],
        ],
        key="overview_label",
    )

    repository = filters[3].selectbox(
        "Repository",
        [
            "All",
            *options["repositories"],
        ],
        key="overview_repository",
    )

    signature = repr(
        (
            search,
            stage,
            signal,
            label,
            repository,
            sort,
        )
    )

    previous_signature = (
        st.session_state.get(
            "overview_filter_signature"
        )
    )

    if previous_signature != signature:
        st.session_state[
            "overview_filter_signature"
        ] = signature

        st.session_state[
            "overview_page"
        ] = 1

    _live_cases_fragment(
        str(settings.db_path),
        search,
        stage,
        signal,
        label,
        repository,
        sort,
    )
