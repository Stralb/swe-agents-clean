from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

import streamlit as st

from src.db.database import Database
from src.pipeline.case_exporter import (
    selected_evidence_zip,
)
from ui.views.insight_data import (
    SCANNER_LABELS,
    fetch_case_page,
    filter_options,
    load_live_overview,
)
from ui.views.research_insights import (
    render_research_map,
)


PAGE_SIZE = 40

POOL_LABELS = {
    "mining": "Mining",
    "cheap_analysis": "Cheap",
    "codeql_security": "CodeQL",
}


def _styles() -> None:
    st.markdown(
        """
<style>
.mim-kpis {
    display:grid;
    grid-template-columns:repeat(5,minmax(130px,1fr));
    gap:.7rem;
    margin:.3rem 0 .8rem 0;
}

.mim-kpi {
    border:1px solid #dbe3ef;
    border-left:5px solid var(--accent);
    border-radius:14px;
    background:white;
    padding:.72rem .82rem;
    box-shadow:0 3px 12px rgba(15,23,42,.05);
}

.mim-kpi-label {
    color:#64748b;
    font-size:.7rem;
    font-weight:850;
    text-transform:uppercase;
    letter-spacing:.04em;
}

.mim-kpi-value {
    color:#0f172a;
    font-size:1.55rem;
    font-weight:950;
}

.mim-pools {
    display:grid;
    grid-template-columns:repeat(3,minmax(170px,1fr));
    gap:.7rem;
}

.mim-pool {
    border:1px solid #dbe3ef;
    border-top:4px solid var(--accent);
    border-radius:13px;
    background:white;
    padding:.62rem .8rem;
}

.mim-pool-name {
    color:#475569;
    font-size:.72rem;
    font-weight:850;
    text-transform:uppercase;
}

.mim-pool-value {
    color:#0f172a;
    font-size:1.25rem;
    font-weight:950;
}

.mim-pool-sub {
    color:#64748b;
    font-size:.7rem;
    font-weight:700;
}

.mim-progress {
    width:100%;
    height:10px;
    background:#e2e8f0;
    border-radius:999px;
    overflow:hidden;
}

.mim-progress > div {
    height:100%;
    width:var(--width);
    background:var(--accent);
    border-radius:999px;
}

.mim-progress-label {
    display:flex;
    justify-content:space-between;
    color:#334155;
    font-size:.76rem;
    font-weight:800;
    margin-bottom:.25rem;
}

.mim-section {
    display:flex;
    align-items:center;
    gap:.4rem;
    margin:1.15rem 0 .55rem;
    color:#0f172a;
    font-size:1.13rem;
    font-weight:950;
}

.mim-info {
    width:17px;
    height:17px;
    border-radius:50%;
    display:inline-flex;
    justify-content:center;
    align-items:center;
    background:#e2e8f0;
    color:#475569;
    font-size:.68rem;
    cursor:help;
}

.mim-region {
    display:inline-block;
    border-radius:999px;
    padding:.18rem .45rem;
    background:#eff6ff;
    color:#1d4ed8;
    font-size:.68rem;
    font-weight:800;
}

@media(max-width:1000px) {
    .mim-kpis {
        grid-template-columns:repeat(2,minmax(130px,1fr));
    }

    .mim-pools {
        grid-template-columns:1fr;
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _section(
    title: str,
    tooltip: str,
) -> None:
    st.markdown(
        (
            "<div class='mim-section'>"
            f"{html.escape(title)}"
            "<span class='mim-info' "
            f"title='{html.escape(tooltip)}'>"
            "i"
            "</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _read_runtime() -> dict[str, Any]:
    path = (
        Path(
            "data/distributed_spool"
        )
        / "status"
        / "autoscaler.json"
    )

    try:
        value = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return (
            value
            if isinstance(
                value,
                dict,
            )
            else {}
        )
    except Exception:
        return {}


# BEGIN MINING SCOPE METRICS
@st.cache_data(
    ttl=5,
    show_spinner=False,
)
def _mining_scope_summary(
    db_path: str,
    database_mtime_ns: int,
) -> dict[str, int]:
    """Return deduplicated, auditable mining scope metrics."""

    import re
    import sqlite3

    del database_mtime_ns

    path = Path(
        db_path
    ).resolve()

    connection = sqlite3.connect(
        f"file:{path}?mode=ro",
        uri=True,
        timeout=10,
    )

    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        completed_repositories: set[str] = set()

        if "retrieval_queries" in tables:
            retrieval_columns = {
                str(row[1])
                for row in connection.execute(
                    """
                    PRAGMA table_info(
                        retrieval_queries
                    )
                    """
                )
            }

            repository_column = None

            for candidate in (
                "repo",
                "repository",
            ):
                if candidate in retrieval_columns:
                    repository_column = candidate
                    break

            query_column = None

            for candidate in (
                "final_query",
                "query",
            ):
                if candidate in retrieval_columns:
                    query_column = candidate
                    break

            if {
                "stream_key",
                "status",
            }.issubset(
                retrieval_columns
            ):
                selected_columns = [
                    "status",
                ]

                if repository_column:
                    selected_columns.append(
                        repository_column
                    )

                if query_column:
                    selected_columns.append(
                        query_column
                    )

                rows = connection.execute(
                    """
                    SELECT
                        """
                    + ", ".join(
                        selected_columns
                    )
                    + """
                    FROM retrieval_queries
                    WHERE stream_key = ?
                    """,
                    (
                        "repo_window",
                    ),
                ).fetchall()

                for row in rows:
                    values = dict(
                        zip(
                            selected_columns,
                            row,
                        )
                    )

                    status = str(
                        values.get(
                            "status"
                        )
                        or ""
                    ).strip().lower()

                    if status not in {
                        "ok",
                        "complete",
                        "completed",
                        "success",
                    }:
                        continue

                    repository = str(
                        values.get(
                            repository_column
                        )
                        or ""
                    ).strip()

                    if (
                        not repository
                        and query_column
                    ):
                        query_text = str(
                            values.get(
                                query_column
                            )
                            or ""
                        )

                        match = re.search(
                            r"(?:^|\s)repo:([^\s]+)",
                            query_text,
                        )

                        if match:
                            repository = (
                                match.group(1)
                            )

                    repository = (
                        repository
                        .strip()
                        .lower()
                    )

                    if repository:
                        completed_repositories.add(
                            repository
                        )

        required_included_tables = {
            "cases",
            "repos",
            "issues",
            "pull_requests",
        }

        included_count = 0
        excluded_count = 0
        touched_count = 0

        if required_included_tables.issubset(
            tables
        ):
            excluded_columns: set[str] = set()

            if "excluded_cases" in tables:
                excluded_columns = {
                    str(row[1])
                    for row in connection.execute(
                        """
                        PRAGMA table_info(
                            excluded_cases
                        )
                        """
                    )
                }

            excluded_repo = (
                "LOWER(TRIM(repo))"
                if "repo" in excluded_columns
                else "''"
            )

            excluded_issue = (
                """
                COALESCE(
                    CAST(issue_number AS TEXT),
                    ''
                )
                """
                if "issue_number"
                in excluded_columns
                else "''"
            )

            excluded_pr = (
                """
                COALESCE(
                    CAST(pr_number AS TEXT),
                    ''
                )
                """
                if "pr_number"
                in excluded_columns
                else "''"
            )

            excluded_source = (
                f"""
                SELECT DISTINCT
                    {excluded_repo}
                        AS repository,
                    {excluded_issue}
                        AS issue_number,
                    {excluded_pr}
                        AS pr_number
                FROM excluded_cases
                WHERE COALESCE(
                    TRIM(repo),
                    ''
                ) <> ''
                """
                if (
                    "excluded_cases" in tables
                    and "repo"
                    in excluded_columns
                )
                else
                """
                SELECT
                    '' AS repository,
                    '' AS issue_number,
                    '' AS pr_number
                WHERE 0
                """
            )

            row = connection.execute(
                f"""
                WITH included_candidates AS (
                    SELECT DISTINCT
                        LOWER(
                            TRIM(r.full_name)
                        ) AS repository,

                        COALESCE(
                            CAST(
                                i.number
                                AS TEXT
                            ),
                            ''
                        ) AS issue_number,

                        COALESCE(
                            CAST(
                                p.number
                                AS TEXT
                            ),
                            ''
                        ) AS pr_number

                    FROM cases AS c

                    JOIN repos AS r
                      ON r.id = c.repo_id

                    JOIN issues AS i
                      ON i.id = c.issue_id

                    JOIN pull_requests AS p
                      ON p.id = c.pr_id

                    WHERE COALESCE(
                        TRIM(r.full_name),
                        ''
                    ) <> ''
                ),

                excluded_candidates AS (
                    {excluded_source}
                ),

                touched_candidates AS (
                    SELECT
                        repository,
                        issue_number,
                        pr_number
                    FROM included_candidates

                    UNION

                    SELECT
                        repository,
                        issue_number,
                        pr_number
                    FROM excluded_candidates
                )

                SELECT
                    (
                        SELECT COUNT(*)
                        FROM included_candidates
                    ) AS included_count,

                    (
                        SELECT COUNT(*)
                        FROM excluded_candidates
                    ) AS excluded_count,

                    (
                        SELECT COUNT(*)
                        FROM touched_candidates
                    ) AS touched_count
                """
            ).fetchone()

            if row:
                included_count = int(
                    row[0] or 0
                )

                excluded_count = int(
                    row[1] or 0
                )

                touched_count = int(
                    row[2] or 0
                )

    finally:
        connection.close()

    return {
        "repositories_scanned": len(
            completed_repositories
        ),
        "included_cases": included_count,
        "excluded_cases": excluded_count,
        "cases_touched": touched_count,
    }


# END MINING SCOPE METRICS


def _render_kpis(
    summary: dict[str, int],
) -> None:
    scope_metrics = (
        (
            "Repos scanned",
            int(
                summary.get(
                    "repositories_scanned",
                    0,
                )
                or 0
            ),
            (
                "Distinct repositories with a completed "
                "imported repo-window search."
            ),
        ),
        (
            "Cases touched",
            int(
                summary.get(
                    "cases_touched",
                    0,
                )
                or 0
            ),
            (
                "Distinct repository, issue and pull-request "
                "candidates seen in either set."
            ),
        ),
        (
            "Included",
            int(
                summary.get(
                    "included_cases",
                    0,
                )
                or 0
            ),
            "Cases stored in the active dataset.",
        ),
        (
            "Excluded",
            int(
                summary.get(
                    "excluded_cases",
                    0,
                )
                or 0
            ),
            (
                "Distinct excluded repository, issue and "
                "pull-request candidates."
            ),
        ),
    )

    scope_cards = []

    for label, value, tooltip in (
        scope_metrics
    ):
        scope_cards.append(
            (
                "<div title='"
                + html.escape(tooltip)
                + "' style='"
                "border:1px solid #e2e8f0;"
                "border-radius:9px;"
                "background:#f8fafc;"
                "padding:.32rem .55rem;"
                "min-height:46px'>"
                "<div style='"
                "font-size:.62rem;"
                "font-weight:800;"
                "letter-spacing:.035em;"
                "text-transform:uppercase;"
                "color:#64748b'>"
                + html.escape(label)
                + "</div>"
                "<div style='"
                "font-size:1rem;"
                "line-height:1.1;"
                "font-weight:900;"
                "color:#0f172a;"
                "margin-top:.08rem'>"
                + f"{value:,}"
                + "</div>"
                "</div>"
            )
        )

    st.markdown(
        (
            "<div style='"
            "display:grid;"
            "grid-template-columns:"
            "repeat(4,minmax(105px,1fr));"
            "gap:.4rem;"
            "margin:0 0 .55rem 0'>"
            + "".join(scope_cards)
            + "</div>"
        ),
        unsafe_allow_html=True,
    )

    columns = st.columns(5)

    metrics = (
        (
            "Cases",
            summary["cases"],
            "All stored issue–pull-request cases.",
        ),
        (
            "Needs review",
            summary["needs_review"],
            "Cases currently routed for manual review.",
        ),
        (
            "Positive cases",
            summary["positive_cases"],
            "Cases containing introduced downstream evidence.",
        ),
        (
            "Reviewed",
            summary["reviewed"],
            "Cases with a saved review label or reviewed state.",
        ),
    )

    for column, (
        label,
        value,
        tooltip,
    ) in zip(
        columns[:4],
        metrics,
    ):
        with column.container(
            border=True
        ):
            st.metric(
                label,
                value,
                help=tooltip,
            )

    with columns[4].container(
        border=True
    ):
        if st.button(
            (
                "Scan problems · "
                + str(
                    summary[
                        "problem_cases"
                    ]
                )
            ),
            width="stretch",
            key="overview-scan-problems",
            help=(
                "Filter the case list to "
                "scanner errors, failures, "
                "timeouts and blocked jobs."
            ),
        ):
            st.session_state[
                "overview_stage"
            ] = "Problems"

            st.session_state[
                "overview_page"
            ] = 1

            st.session_state.pop(
                "overview_pattern_case_ids",
                None,
            )

            st.session_state.pop(
                "overview_pattern_label",
                None,
            )

            st.rerun()


def _render_pools() -> None:
    runtime = _read_runtime()

    pools = runtime.get(
        "pools",
        {},
    )

    if not isinstance(
        pools,
        dict,
    ):
        pools = {}

    cards = []

    for pool in (
        "mining",
        "cheap_analysis",
        "codeql_security",
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

        active = int(
            details.get(
                "active_workers"
            )
            or 0
        )

        desired = int(
            details.get(
                "desired_workers"
            )
            or 0
        )

        queued = int(
            counts.get("pending")
            or 0
        ) + int(
            counts.get("claimed")
            or 0
        )

        color = (
            "#16a34a"
            if active == desired
            else "#d97706"
        )

        cards.append(
            (
                "<div class='mim-pool' "
                f"style='--accent:{color}' "
                f"title='{POOL_LABELS[pool]}: "
                f"{active} active, "
                f"{desired} desired, "
                f"{queued} queued'>"
                "<div class='mim-pool-name'>"
                f"{POOL_LABELS[pool]}"
                "</div>"
                "<div class='mim-pool-value'>"
                f"{active}/{desired}"
                "</div>"
                "<div class='mim-pool-sub'>"
                f"{queued} queued"
                "</div>"
                "</div>"
            )
        )

    st.markdown(
        (
            "<div class='mim-pools'>"
            + "".join(cards)
            + "</div>"
        ),
        unsafe_allow_html=True,
    )


def _progress_html(
    *,
    label: str,
    terminal: int,
    eligible: int,
    color: str,
    tooltip: str,
) -> str:
    percentage = (
        terminal
        / eligible
        * 100
        if eligible
        else 0.0
    )

    return (
        "<div "
        f"title='{html.escape(tooltip)}'>"
        "<div class='mim-progress-label'>"
        f"<span>{html.escape(label)}</span>"
        f"<span>{terminal}/{eligible}"
        f" · {percentage:.1f}%</span>"
        "</div>"
        "<div class='mim-progress' "
        f"style='--accent:{color}'>"
        "<div "
        f"style='--width:{percentage:.3f}%'>"
        "</div>"
        "</div>"
        "</div>"
    )


def _open_scanner(
    scanner: str,
) -> None:
    st.session_state[
        "selected_scanner"
    ] = scanner

    st.session_state["nav"] = (
        "Scanner Insights"
    )

    st.rerun()


def _render_scanners(
    payload: dict[str, Any],
) -> None:
    cheap = payload["cheap"]

    st.markdown(
        _progress_html(
            label=(
                "Cheap scanner aggregate"
            ),
            terminal=int(
                cheap["terminal"]
            ),
            eligible=int(
                cheap["eligible"]
            ),
            color="#2563eb",
            tooltip=(
                "A case is complete when every "
                "cheap scanner routed to that case "
                "has a terminal latest result."
            ),
        ),
        unsafe_allow_html=True,
    )

    scanner_rows = {
        row["scanner"]: row
        for row in payload["scanners"]
    }

    for scanner in (
        "gitleaks",
        "dependency-diff",
        "osv-scanner",
        "semgrep",
        "trivy",
    ):
        row = scanner_rows.get(
            scanner
        )

        if not row:
            continue

        if (
            int(row["eligible"]) == 0
            and int(row["findings"]) == 0
        ):
            continue

        columns = st.columns(
            [
                1.2,
                4.6,
                1,
                1,
            ]
        )

        if columns[0].button(
            row["label"],
            key=(
                "overview-scanner-"
                + scanner
            ),
            width="stretch",
            help=(
                "Open scanner-specific findings, "
                "regions, rules, repositories and "
                "matching cases."
            ),
        ):
            _open_scanner(scanner)

        percentage = (
            int(row["terminal"])
            / int(row["eligible"])
            * 100
            if int(
                row["eligible"]
            )
            else 0.0
        )

        columns[1].progress(
            min(
                1.0,
                max(
                    0.0,
                    percentage / 100,
                ),
            ),
            text=(
                f"{row['terminal']}/"
                f"{row['eligible']} eligible"
            ),
        )

        columns[2].metric(
            "Findings",
            row["findings"],
            help=(
                "Stored findings produced by "
                "this scanner."
            ),
        )

        columns[3].metric(
            "Errors",
            row["errors"],
            help=(
                "Eligible cases whose latest "
                "run ended in an error state."
            ),
        )

    codeql = scanner_rows.get(
        "codeql",
        {
            "eligible": 0,
            "terminal": 0,
            "findings": 0,
            "errors": 0,
            "label": "CodeQL",
        },
    )

    st.markdown(
        _progress_html(
            label="CodeQL aggregate",
            terminal=int(
                codeql["terminal"]
            ),
            eligible=int(
                codeql["eligible"]
            ),
            color="#7c3aed",
            tooltip=(
                "Terminal CodeQL results divided "
                "by cases routed or submitted to "
                "CodeQL."
            ),
        ),
        unsafe_allow_html=True,
    )

    button_columns = st.columns(
        [
            1.2,
            4.6,
            1,
            1,
        ]
    )

    if button_columns[0].button(
        "CodeQL",
        key="overview-scanner-codeql",
        width="stretch",
        help=(
            "Open CodeQL rules, CWE data, "
            "regions, repositories and cases."
        ),
    ):
        _open_scanner(
            "codeql"
        )

    button_columns[1].progress(
        (
            int(codeql["terminal"])
            / int(codeql["eligible"])
            if int(
                codeql["eligible"]
            )
            else 0.0
        ),
        text=(
            f"{codeql['terminal']}/"
            f"{codeql['eligible']} eligible"
        ),
    )

    button_columns[2].metric(
        "Findings",
        codeql["findings"],
    )

    button_columns[3].metric(
        "Errors",
        codeql["errors"],
    )


def _live_status(
    db_path: str,
) -> None:
    payload = load_live_overview(
        db_path
    )

    database_path = Path(
        db_path
    )

    payload["summary"].update(
        _mining_scope_summary(
            db_path,
            database_path.stat().st_mtime_ns,
        )
    )

    _render_kpis(
        payload["summary"]
    )

    _section(
        "Worker pools",
        (
            "Compact active/desired worker "
            "counts. Configuration remains on "
            "the Runtime page."
        ),
    )

    _render_pools()

    _section(
        "Scanner coverage",
        (
            "Coverage uses eligible routed "
            "cases, not every case in the "
            "database."
        ),
    )

    _render_scanners(
        payload
    )


if hasattr(st, "fragment"):
    @st.fragment(
        run_every="3s"
    )
    def _live_status_fragment(
        db_path: str,
    ) -> None:
        _live_status(
            db_path
        )


    @st.fragment(
        run_every="15s"
    )
    def _research_fragment(
        db_path: str,
    ) -> None:
        render_research_map(
            db_path
        )
else:
    def _live_status_fragment(
        db_path: str,
    ) -> None:
        _live_status(
            db_path
        )


    def _research_fragment(
        db_path: str,
    ) -> None:
        render_research_map(
            db_path
        )


def _selected_ids() -> set[int]:
    return {
        int(value)
        for value in st.session_state.get(
            "overview_selected_case_ids",
            [],
        )
    }


def _store_selected(
    values: set[int],
) -> None:
    st.session_state[
        "overview_selected_case_ids"
    ] = sorted(values)


def _open_case(
    case_id: int,
    queue: list[int],
) -> None:
    st.session_state[
        "selected_case_id"
    ] = int(case_id)

    st.session_state[
        "review_queue_ids"
    ] = [
        int(value)
        for value in queue
    ]

    st.session_state["nav"] = (
        "Case Review"
    )

    st.rerun()


def _case_fragment(
    *,
    db_path: str,
    search: str,
    stage: str,
    region: str,
    repository: str,
    sort: str,
) -> None:
    page = max(
        1,
        int(
            st.session_state.get(
                "overview_page",
                1,
            )
        ),
    )

    total, rows = fetch_case_page(
        db_path,
        search=search,
        stage=stage,
        region=region,
        repository=repository,
        sort=sort,
        page=page,
        page_size=PAGE_SIZE,
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

    visible_ids = [
        int(row["case_id"])
        for row in rows
    ]

    selected = _selected_ids()

    toolbar = st.columns(
        [
            1.1,
            1.1,
            1.25,
            1.35,
            2.4,
        ]
    )

    if toolbar[0].button(
        "Select visible",
        key="overview-select-visible",
    ):
        selected.update(
            visible_ids
        )

        _store_selected(
            selected
        )

        st.rerun()

    if toolbar[1].button(
        "Clear",
        key="overview-clear-selection",
    ):
        selected.clear()

        _store_selected(
            selected
        )

        st.session_state.pop(
            "overview_prepared_zip",
            None,
        )

        st.rerun()

    if toolbar[2].button(
        "Review selected",
        disabled=not selected,
        key="overview-review-selected",
    ):
        queue = sorted(
            selected
        )

        _open_case(
            queue[0],
            queue,
        )

    if toolbar[3].button(
        "Prepare ZIP",
        disabled=not selected,
        key="overview-prepare-zip",
        help=(
            "Generate evidence only when "
            "pressed. It is not rebuilt during "
            "auto-refresh."
        ),
    ):
        st.session_state[
            "overview_prepared_zip"
        ] = selected_evidence_zip(
            Database(
                Path(db_path)
            ),
            sorted(selected),
        )

    prepared = st.session_state.get(
        "overview_prepared_zip"
    )

    if prepared is not None:
        toolbar[4].download_button(
            "Download selected evidence",
            data=prepared,
            file_name=(
                "selected_cases_evidence.zip"
            ),
            mime="application/zip",
            width="stretch",
            key="overview-download-zip",
        )
    else:
        toolbar[4].markdown(
            f"**{len(selected)} selected**"
        )

    start = (
        (page - 1)
        * PAGE_SIZE
        + 1
        if total
        else 0
    )

    end = min(
        total,
        page * PAGE_SIZE,
    )

    st.caption(
        f"{start}–{end} of {total}"
    )

    for row in rows:
        case_id = int(
            row["case_id"]
        )

        columns = st.columns(
            [
                0.42,
                0.6,
                1.65,
                3.9,
                1.7,
                0.72,
                0.72,
                0.82,
            ]
        )

        checked = columns[0].checkbox(
            "Select",
            value=(
                case_id in selected
            ),
            key=(
                "overview-case-select-"
                f"{case_id}"
            ),
            label_visibility="collapsed",
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

        region_text = str(
            row.get("regions")
            or "Unknown"
        )

        columns[4].markdown(
            (
                "<span class='mim-region' "
                "title='Persisted multi-label "
                "artifact regions'>"
                f"{html.escape(region_text)}"
                "</span>"
            ),
            unsafe_allow_html=True,
        )

        columns[5].metric(
            "All",
            int(
                row.get(
                    "finding_count"
                )
                or 0
            ),
            help="Stored scanner findings.",
        )

        columns[6].metric(
            "New",
            int(
                row.get(
                    "introduced_count"
                )
                or 0
            ),
            help=(
                "Findings present in head but "
                "not in base."
            ),
        )

        if columns[7].button(
            "Inspect",
            key=(
                "overview-inspect-"
                f"{case_id}"
            ),
            width="stretch",
        ):
            _open_case(
                case_id,
                visible_ids,
            )

    _store_selected(
        selected
    )

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
        key="overview-previous",
        width="stretch",
    ):
        st.session_state[
            "overview_page"
        ] = page - 1

        st.rerun()

    centre.markdown(
        (
            "<div style='text-align:center;"
            "padding-top:.45rem'>"
            f"<strong>Page {page} of "
            f"{total_pages}</strong>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    if next_page.button(
        "Next",
        disabled=(
            page >= total_pages
        ),
        key="overview-next",
        width="stretch",
    ):
        st.session_state[
            "overview_page"
        ] = page + 1

        st.rerun()


if hasattr(st, "fragment"):
    _live_cases_fragment = st.fragment(
        _case_fragment,
        run_every="3s",
    )
else:
    _live_cases_fragment = (
        _case_fragment
    )


def render_overview_fast(
    settings: Any,
) -> None:
    _styles()

    _, runtime = st.columns(
        [
            5,
            1,
        ]
    )

    if runtime.button(
        "Runtime",
        width="stretch",
        help=(
            "Open scheduling mode, pool "
            "toggles and thresholds."
        ),
    ):
        st.session_state["nav"] = (
            "Runtime"
        )

        st.rerun()

    db_path = str(
        settings.db_path
    )

    _live_status_fragment(
        db_path
    )

    _section(
        "Evidence yield map",
        (
            "Maps AI indicators, file facts, "
            "path rules, regions and scanner "
            "routes against eligible coverage "
            "and downstream-positive yield."
        ),
    )

    _research_fragment(
        db_path
    )

    _section(
        "Cases",
        (
            "Only forty lightweight records "
            "are loaded. Full evidence opens "
            "on the separate Case Review page."
        ),
    )

    options = filter_options(
        db_path
    )

    first_row = st.columns(
        [
            4,
            1.25,
        ]
    )

    search = first_row[0].text_input(
        "Search",
        placeholder=(
            "Case ID, repository or issue title"
        ),
        key="overview_search",
    )

    sort = first_row[1].selectbox(
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

    filters = st.columns(3)

    stage = filters[0].selectbox(
        "Case set",
        [
            "All",
            "Needs review",
            "Positive evidence",
            "Reviewed",
            "Problems",
            "In progress",
        ],
        key="overview_stage",
    )

    region = filters[1].selectbox(
        "Region",
        [
            "All",
            *options["regions"],
        ],
        key="overview_region",
    )

    repository = filters[2].selectbox(
        "Repository",
        [
            "All",
            *options[
                "repositories"
            ],
        ],
        key="overview_repository",
    )

    signature = repr(
        (
            search,
            stage,
            region,
            repository,
            sort,
        )
    )

    if (
        st.session_state.get(
            "overview_filter_signature"
        )
        != signature
    ):
        st.session_state[
            "overview_filter_signature"
        ] = signature

        st.session_state[
            "overview_page"
        ] = 1

    _live_cases_fragment(
        db_path=db_path,
        search=search,
        stage=stage,
        region=region,
        repository=repository,
        sort=sort,
    )
