from __future__ import annotations

import html
import json
import math
import time
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

from src.db.database import Database

# Reuse the original, verified case-level scanner coverage logic.
# It evaluates the latest run of every scanner for every case,
# rather than counting scanner_jobs rows.
from ui.views.overview import _scan_progress_data


PAGE_SIZE = 40

POOL_LABELS = {
    "mining": "Mining",
    "cheap_analysis": "Cheap",
    "codeql_security": "CodeQL",
}

STAGE_COLORS = {
    "Needs review": "#dc2626",
    "Blocked": "#ea580c",
    "Scanning": "#7c3aed",
    "Validated": "#2563eb",
    "Clean": "#16a34a",
    "Reviewed": "#0891b2",
}

SIGNAL_COLORS = {
    "pending": "#64748b",
    "clean": "#16a34a",
    "source-code": "#2563eb",
    "codeql": "#7c3aed",
    "secret/ci": "#dc2626",
    "dependency": "#d97706",
}

STAGE_SQL = """
CASE
    WHEN c.status = 'needs_review'
    THEN 'Needs review'

    WHEN c.status = 'reviewed'
    THEN 'Reviewed'

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


def _inject_styles() -> None:
    st.markdown(
        """
<style>
.mim-section-title {
    display:flex;
    align-items:center;
    gap:.42rem;
    margin:1.15rem 0 .55rem 0;
    color:#0f172a;
    font-size:1.12rem;
    font-weight:900;
}

.mim-info {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:17px;
    height:17px;
    border-radius:50%;
    background:#e2e8f0;
    color:#475569;
    font-size:.69rem;
    font-weight:900;
    cursor:help;
}

.mim-kpi-grid {
    display:grid;
    grid-template-columns:repeat(6,minmax(120px,1fr));
    gap:.68rem;
    margin:.25rem 0 .75rem 0;
}

.mim-kpi {
    position:relative;
    overflow:hidden;
    border:1px solid #e2e8f0;
    border-radius:15px;
    background:#ffffff;
    padding:.78rem .85rem .72rem .85rem;
    box-shadow:0 4px 14px rgba(15,23,42,.055);
}

.mim-kpi::before {
    content:"";
    position:absolute;
    left:0;
    top:0;
    bottom:0;
    width:5px;
    background:var(--mim-color);
}

.mim-kpi-label {
    color:#64748b;
    font-size:.72rem;
    font-weight:800;
    text-transform:uppercase;
    letter-spacing:.035em;
    white-space:nowrap;
}

.mim-kpi-value {
    margin-top:.13rem;
    color:#0f172a;
    font-size:1.55rem;
    line-height:1.1;
    font-weight:950;
}

.mim-runtime-grid {
    display:grid;
    grid-template-columns:repeat(4,minmax(150px,1fr));
    gap:.68rem;
}

.mim-runtime-card {
    border:1px solid #e2e8f0;
    border-top:4px solid var(--mim-color);
    border-radius:14px;
    background:#ffffff;
    padding:.7rem .82rem;
    box-shadow:0 3px 12px rgba(15,23,42,.045);
}

.mim-runtime-title {
    color:#475569;
    font-size:.75rem;
    font-weight:850;
    text-transform:uppercase;
}

.mim-runtime-value {
    color:#0f172a;
    font-size:1.35rem;
    font-weight:950;
}

.mim-runtime-detail {
    margin-top:.15rem;
    color:#64748b;
    font-size:.72rem;
    font-weight:700;
}

.mim-progress-shell {
    margin:.62rem 0;
}

.mim-progress-head {
    display:flex;
    justify-content:space-between;
    gap:1rem;
    color:#334155;
    font-size:.79rem;
    font-weight:850;
    margin-bottom:.27rem;
}

.mim-progress-track {
    width:100%;
    height:13px;
    border-radius:999px;
    background:#e2e8f0;
    overflow:hidden;
}

.mim-progress-fill {
    height:100%;
    border-radius:999px;
    background:var(--mim-color);
    transition:width .25s ease;
}

.mim-progress-foot {
    display:flex;
    gap:.9rem;
    flex-wrap:wrap;
    margin-top:.28rem;
    color:#64748b;
    font-size:.69rem;
    font-weight:700;
}

.mim-pill {
    display:inline-block;
    max-width:100%;
    padding:.22rem .52rem;
    border-radius:999px;
    border:1px solid var(--mim-color);
    background:color-mix(
        in srgb,
        var(--mim-color) 10%,
        white
    );
    color:var(--mim-color);
    font-size:.7rem;
    line-height:1.05rem;
    font-weight:850;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}

.mim-page-state {
    display:inline-block;
    border:1px solid #dbeafe;
    background:#eff6ff;
    color:#1d4ed8;
    border-radius:999px;
    padding:.22rem .56rem;
    font-size:.72rem;
    font-weight:800;
}

.mim-live {
    display:inline-block;
    border:1px solid #bbf7d0;
    background:#f0fdf4;
    color:#15803d;
    border-radius:999px;
    padding:.22rem .56rem;
    font-size:.7rem;
    font-weight:850;
    cursor:help;
}

@media (max-width:1200px) {
    .mim-kpi-grid {
        grid-template-columns:repeat(3,minmax(120px,1fr));
    }

    .mim-runtime-grid {
        grid-template-columns:repeat(2,minmax(150px,1fr));
    }
}

@media (max-width:760px) {
    .mim-kpi-grid,
    .mim-runtime-grid {
        grid-template-columns:repeat(2,minmax(120px,1fr));
    }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _section_title(
    label: str,
    tooltip: str,
) -> None:
    st.markdown(
        (
            "<div class='mim-section-title'>"
            f"{html.escape(label)}"
            "<span class='mim-info' "
            f"title='{html.escape(tooltip)}'>"
            "i"
            "</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _pill(
    value: Any,
    color: str,
    tooltip: str,
) -> str:
    text = str(value or "")

    return (
        "<span class='mim-pill' "
        f"style='--mim-color:{html.escape(color)}' "
        f"title='{html.escape(tooltip)}'>"
        f"{html.escape(text)}"
        "</span>"
    )


def _summary(
    db: Database,
) -> dict[str, int]:
    cases = _safe_one(
        db,
        f"""
        WITH staged AS (
            SELECT
                ({STAGE_SQL}) AS stage
            FROM cases c
        )

        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN stage = 'Needs review'
                    THEN 1
                    ELSE 0
                END
            ) AS needs_review,

            SUM(
                CASE
                    WHEN stage IN (
                        'Validated',
                        'Scanning',
                        'Blocked'
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS in_progress,

            SUM(
                CASE
                    WHEN stage = 'Clean'
                    THEN 1
                    ELSE 0
                END
            ) AS clean,

            SUM(
                CASE
                    WHEN stage = 'Reviewed'
                    THEN 1
                    ELSE 0
                END
            ) AS reviewed

        FROM staged
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
        "findings": _integer(
            findings.get("findings")
        ),
        "introduced": _integer(
            findings.get("introduced")
        ),
    }


def _chart_data(
    db: Database,
) -> dict[str, list[dict[str, Any]]]:
    signals = _safe_query(
        db,
        """
        SELECT
            LOWER(
                COALESCE(
                    NULLIF(
                        downstream_signal,
                        ''
                    ),
                    'pending'
                )
            ) AS category,

            COUNT(*) AS value

        FROM cases

        GROUP BY category
        ORDER BY value DESC, category
        """,
    )

    scanner_findings = _safe_query(
        db,
        """
        SELECT
            COALESCE(
                NULLIF(scanner, ''),
                'unknown'
            ) AS scanner,

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

        GROUP BY scanner
        ORDER BY introduced DESC, findings DESC, scanner
        """,
    )

    regions = _safe_query(
        db,
        """
        WITH memberships AS (
            SELECT DISTINCT
                case_id,
                region
            FROM artifact_regions
        )

        SELECT
            memberships.region,

            COUNT(*) AS pairs,

            SUM(
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM scanner_findings sf
                        WHERE sf.case_id =
                              memberships.case_id
                          AND COALESCE(
                                sf.introduced,
                                0
                              ) = 1
                    )
                    THEN 1
                    ELSE 0
                END
            ) AS introduced_pairs

        FROM memberships

        GROUP BY memberships.region

        ORDER BY
            introduced_pairs DESC,
            pairs DESC,
            memberships.region

        LIMIT 10
        """,
    )

    return {
        "signals": signals,
        "scanner_findings": scanner_findings,
        "regions": regions,
    }


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

    scan_summary, scanner_table = (
        _scan_progress_data(db)
    )

    return {
        "summary": _summary(db),
        "runtime": runtime,
        "scan_summary": scan_summary,
        "scanner_rows": (
            scanner_table.to_dict(
                orient="records"
            )
        ),
        "charts": _chart_data(db),
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

        if value and value not in values:
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

    count_row = _safe_one(
        db,
        f"""
        SELECT
            COUNT(*) AS n

        FROM cases c

        JOIN repos r
          ON r.id = c.repo_id

        JOIN issues i
          ON i.id = c.issue_id

        {where_sql}
        """,
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
        f"""
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

            LOWER(
                COALESCE(
                    NULLIF(
                        c.downstream_signal,
                        ''
                    ),
                    'pending'
                )
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
        """,
        tuple(page_parameters),
    )

    return total, rows


def _render_summary(
    summary: dict[str, int],
) -> None:
    cards = (
        (
            "Cases",
            summary["total"],
            "#2563eb",
            "All valid issue–pull-request cases in the current database.",
        ),
        (
            "Needs review",
            summary["needs_review"],
            "#dc2626",
            "Cases whose current pipeline status is needs_review.",
        ),
        (
            "In pipeline",
            summary["in_progress"],
            "#7c3aed",
            "Validated, scanning or blocked cases that have not reached a terminal state.",
        ),
        (
            "Clean",
            summary["clean"],
            "#16a34a",
            "Cases whose current pipeline status is scanned_clean.",
        ),
        (
            "Reviewed",
            summary["reviewed"],
            "#0891b2",
            "Cases whose current pipeline status is reviewed.",
        ),
        (
            "Introduced",
            summary["introduced"],
            "#db2777",
            "Stored findings classified as introduced by the pull request.",
        ),
    )

    body = []

    for label, value, color, tooltip in cards:
        body.append(
            "<div class='mim-kpi' "
            f"style='--mim-color:{color}' "
            f"title='{html.escape(tooltip)}'>"
            f"<div class='mim-kpi-label'>{html.escape(label)}</div>"
            f"<div class='mim-kpi-value'>{value}</div>"
            "</div>"
        )

    st.markdown(
        "<div class='mim-kpi-grid'>"
        + "".join(body)
        + "</div>",
        unsafe_allow_html=True,
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
        st.warning(
            "Runtime status unavailable.",
            icon="⚠️",
        )
        return

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
            details.get("active_workers")
        )

        desired = _integer(
            details.get("desired_workers")
        )

        pending = _integer(
            counts.get("pending")
        )

        claimed = _integer(
            counts.get("claimed")
        )

        backlog = pending + claimed

        if active == desired:
            color = "#16a34a"
            state = "On target"
        elif active < desired:
            color = "#d97706"
            state = "Scaling up"
        else:
            color = "#dc2626"
            state = "Draining"

        tooltip = (
            f"{POOL_LABELS[pool]} pool: "
            f"{active} active, {desired} desired, "
            f"{pending} pending and {claimed} claimed."
        )

        cards.append(
            "<div class='mim-runtime-card' "
            f"style='--mim-color:{color}' "
            f"title='{html.escape(tooltip)}'>"
            f"<div class='mim-runtime-title'>{POOL_LABELS[pool]}</div>"
            f"<div class='mim-runtime-value'>{active}/{desired}</div>"
            f"<div class='mim-runtime-detail'>{backlog} queued · {state}</div>"
            "</div>"
        )

    allocation = runtime.get(
        "allocation",
        {},
    )

    if not isinstance(
        allocation,
        dict,
    ):
        allocation = {}

    allocated = _integer(
        allocation.get("allocated_workers")
    )

    budget = _integer(
        allocation.get("worker_budget")
    )

    mode = str(
        allocation.get("mode")
        or "unknown"
    ).title()

    scheduler_color = (
        "#16a34a"
        if allocated <= budget
        else "#dc2626"
    )

    cards.append(
        "<div class='mim-runtime-card' "
        f"style='--mim-color:{scheduler_color}' "
        "title='Scheduler mode and total worker-budget allocation.'>"
        "<div class='mim-runtime-title'>Scheduler</div>"
        f"<div class='mim-runtime-value'>{html.escape(mode)}</div>"
        f"<div class='mim-runtime-detail'>{allocated}/{budget} allocated</div>"
        "</div>"
    )

    st.markdown(
        "<div class='mim-runtime-grid'>"
        + "".join(cards)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_progress(
    summary: dict[str, Any],
    scanner_rows: list[dict[str, Any]],
) -> None:
    total = _integer(
        summary.get("total")
    )

    items = (
        (
            "Cheap scanner coverage",
            _integer(
                summary.get("cheap_finished")
            ),
            "#2563eb",
            "A case is complete only when the latest Gitleaks, dependency-diff, OSV and Semgrep runs are all terminal. not_applicable is terminal.",
        ),
        (
            "CodeQL coverage",
            _integer(
                summary.get("codeql_finished")
            ),
            "#7c3aed",
            "Cases with a terminal latest CodeQL run. Errors are terminal for coverage but remain visible in scanner detail.",
        ),
    )

    for label, finished, color, tooltip in items:
        percentage = (
            finished / total * 100
            if total
            else 0.0
        )

        pending = max(
            0,
            total - finished,
        )

        st.markdown(
            (
                "<div class='mim-progress-shell' "
                f"title='{html.escape(tooltip)}'>"
                "<div class='mim-progress-head'>"
                f"<span>{html.escape(label)}</span>"
                f"<span>{finished}/{total} · {percentage:.1f}%</span>"
                "</div>"
                "<div class='mim-progress-track'>"
                "<div class='mim-progress-fill' "
                f"style='--mim-color:{color};width:{percentage:.3f}%'>"
                "</div>"
                "</div>"
                "<div class='mim-progress-foot'>"
                f"<span>{pending} without terminal coverage</span>"
                "</div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

    problem_cases = _integer(
        summary.get("problem_cases")
    )

    active_jobs = _integer(
        summary.get("active_jobs")
    )

    stored_findings = _integer(
        summary.get("findings")
    )

    columns = st.columns(3)

    columns[0].metric(
        "Scan problems",
        problem_cases,
        help=(
            "Cases whose latest scanner states include "
            "an error, timeout, missing tool, parse failure "
            "or partial result."
        ),
    )

    columns[1].metric(
        "Active jobs",
        active_jobs,
        help=(
            "Scanner jobs currently pending, retrying "
            "or running."
        ),
    )

    columns[2].metric(
        "Stored findings",
        stored_findings,
        help=(
            "All currently persisted scanner findings."
        ),
    )

    with st.expander(
        "Scanner detail",
        expanded=False,
    ):
        st.dataframe(
            pd.DataFrame(scanner_rows),
            hide_index=True,
            width="stretch",
        )


def _render_charts(
    chart_data: dict[str, list[dict[str, Any]]],
) -> None:
    signal_column, scanner_column, region_column = (
        st.columns(3)
    )

    signals = pd.DataFrame(
        chart_data.get(
            "signals",
            [],
        )
    )

    with signal_column:
        _section_title(
            "Signal mix",
            "Distribution of the current downstream signal assigned to each case.",
        )

        if signals.empty:
            st.info("No signal data.")
        else:
            signals["value"] = pd.to_numeric(
                signals["value"],
                errors="coerce",
            ).fillna(0)

            signal_order = list(
                signals["category"]
            )

            signal_colors = [
                SIGNAL_COLORS.get(
                    str(value).lower(),
                    "#64748b",
                )
                for value in signal_order
            ]

            chart = (
                alt.Chart(signals)
                .mark_arc(
                    innerRadius=48,
                    outerRadius=88,
                )
                .encode(
                    theta=alt.Theta(
                        "value:Q",
                        stack=True,
                    ),
                    color=alt.Color(
                        "category:N",
                        scale=alt.Scale(
                            domain=signal_order,
                            range=signal_colors,
                        ),
                        legend=alt.Legend(
                            title=None,
                            orient="bottom",
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "category:N",
                            title="Signal",
                        ),
                        alt.Tooltip(
                            "value:Q",
                            title="Cases",
                            format=",",
                        ),
                    ],
                )
                .properties(
                    height=240,
                )
            )

            st.altair_chart(
                chart,
                width="stretch",
            )

    findings = pd.DataFrame(
        chart_data.get(
            "scanner_findings",
            [],
        )
    )

    with scanner_column:
        _section_title(
            "Findings by scanner",
            "Grey shows all stored findings. Red shows the introduced subset.",
        )

        if findings.empty:
            st.info("No stored findings.")
        else:
            for column in (
                "findings",
                "introduced",
            ):
                findings[column] = pd.to_numeric(
                    findings[column],
                    errors="coerce",
                ).fillna(0)

            order = list(
                findings.sort_values(
                    [
                        "findings",
                        "introduced",
                    ],
                    ascending=False,
                )["scanner"]
            )

            base = (
                alt.Chart(findings)
                .mark_bar(
                    color="#cbd5e1",
                    cornerRadiusEnd=4,
                )
                .encode(
                    y=alt.Y(
                        "scanner:N",
                        sort=order,
                        title=None,
                    ),
                    x=alt.X(
                        "findings:Q",
                        title="Stored findings",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "scanner:N",
                            title="Scanner",
                        ),
                        alt.Tooltip(
                            "findings:Q",
                            title="All findings",
                            format=",",
                        ),
                        alt.Tooltip(
                            "introduced:Q",
                            title="Introduced",
                            format=",",
                        ),
                    ],
                )
            )

            introduced = (
                alt.Chart(findings)
                .mark_bar(
                    color="#ef4444",
                    cornerRadiusEnd=4,
                )
                .encode(
                    y=alt.Y(
                        "scanner:N",
                        sort=order,
                        title=None,
                    ),
                    x=alt.X(
                        "introduced:Q",
                        title="Stored findings",
                    ),
                )
            )

            st.altair_chart(
                alt.layer(
                    base,
                    introduced,
                ).properties(
                    height=240,
                ),
                width="stretch",
            )

    regions = pd.DataFrame(
        chart_data.get(
            "regions",
            [],
        )
    )

    with region_column:
        _section_title(
            "Artifact-region yield",
            "Blue shows cases mapped to a region. Pink shows cases in that region with introduced evidence.",
        )

        if regions.empty:
            st.info("No artifact-region data.")
        else:
            for column in (
                "pairs",
                "introduced_pairs",
            ):
                regions[column] = pd.to_numeric(
                    regions[column],
                    errors="coerce",
                ).fillna(0)

            order = list(
                regions.sort_values(
                    [
                        "introduced_pairs",
                        "pairs",
                    ],
                    ascending=False,
                )["region"]
            )

            base = (
                alt.Chart(regions)
                .mark_bar(
                    color="#93c5fd",
                    cornerRadiusEnd=4,
                )
                .encode(
                    y=alt.Y(
                        "region:N",
                        sort=order,
                        title=None,
                    ),
                    x=alt.X(
                        "pairs:Q",
                        title="Cases",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "region:N",
                            title="Region",
                        ),
                        alt.Tooltip(
                            "pairs:Q",
                            title="Mapped cases",
                            format=",",
                        ),
                        alt.Tooltip(
                            "introduced_pairs:Q",
                            title="Introduced cases",
                            format=",",
                        ),
                    ],
                )
            )

            introduced = (
                alt.Chart(regions)
                .mark_bar(
                    color="#db2777",
                    cornerRadiusEnd=4,
                )
                .encode(
                    y=alt.Y(
                        "region:N",
                        sort=order,
                        title=None,
                    ),
                    x=alt.X(
                        "introduced_pairs:Q",
                        title="Cases",
                    ),
                )
            )

            st.altair_chart(
                alt.layer(
                    base,
                    introduced,
                ).properties(
                    height=240,
                ),
                width="stretch",
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

    _section_title(
        "Pipeline",
        "Current worker allocation, desired allocation and queued work from the autoscaler.",
    )

    _render_runtime(
        payload["runtime"]
    )

    _section_title(
        "Scanner coverage",
        "Coverage is calculated from the latest case-level run of every required scanner, not from the number of job records.",
    )

    _render_progress(
        payload["scan_summary"],
        payload["scanner_rows"],
    )

    _section_title(
        "Live charts",
        "Compact analytical views that do not repeat the headline case-stage metrics.",
    )

    _render_charts(
        payload["charts"]
    )

    refreshed = time.strftime(
        "%H:%M:%S",
        time.localtime(
            payload["loaded_at"]
        ),
    )

    st.markdown(
        (
            "<span class='mim-live' "
            "title='Statistics, worker state, scanner coverage "
            "and charts refresh every three seconds without "
            "rerunning the filter controls.'>"
            f"● Live · {refreshed}"
            "</span>"
        ),
        unsafe_allow_html=True,
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

    st.session_state["nav"] = (
        "Case Review"
    )

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

        stage = str(
            row.get("stage")
            or "Validated"
        )

        signal = str(
            row.get("signal")
            or "pending"
        )

        label = str(
            row.get("label")
            or "Unreviewed"
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

            columns[3].markdown(
                _pill(
                    stage,
                    STAGE_COLORS.get(
                        stage,
                        "#64748b",
                    ),
                    "Current pipeline stage.",
                ),
                unsafe_allow_html=True,
            )

            columns[4].markdown(
                _pill(
                    signal,
                    SIGNAL_COLORS.get(
                        signal.lower(),
                        "#64748b",
                    ),
                    "Current downstream evidence signal.",
                ),
                unsafe_allow_html=True,
            )

            label_color = (
                "#64748b"
                if label == "Unreviewed"
                else "#0891b2"
            )

            columns[5].markdown(
                _pill(
                    label,
                    label_color,
                    "Current final or provisional case label.",
                ),
                unsafe_allow_html=True,
            )

            columns[6].markdown(
                (
                    "<div style='text-align:center;"
                    "font-weight:900;color:#334155' "
                    "title='Number of stored findings for this case.'>"
                    f"{_integer(row.get('finding_count'))}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

            if columns[7].button(
                "Inspect",
                key=(
                    f"overview-inspect-{case_id}"
                ),
                width="stretch",
                help=(
                    "Open this case in the existing "
                    "Case Review interface."
                ),
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
    page = max(
        1,
        _integer(
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
        if total
        else 0
    )

    last_row = min(
        total,
        page * PAGE_SIZE,
    )

    st.markdown(
        (
            "<span class='mim-page-state' "
            "title='Only this forty-row result window is loaded.'>"
            f"{total} cases · {first_row}–{last_row}"
            "</span>"
        ),
        unsafe_allow_html=True,
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
    _inject_styles()

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

    if runtime_column.button(
        "Runtime controls",
        width="stretch",
        key="overview-runtime-controls",
        help=(
            "Open automatic/manual scheduling, "
            "pool toggles, worker limits and "
            "threshold configuration."
        ),
    ):
        st.session_state["nav"] = (
            "Runtime"
        )

        st.rerun()

    _live_status_fragment(
        str(settings.db_path),
        "data/distributed_spool",
    )

    _section_title(
        "Cases",
        "Search and filter lightweight case records. Full evidence loads only after Inspect is selected.",
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
        help=(
            "Search is executed in SQLite "
            "against the lightweight case list."
        ),
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
        help=(
            "Priority places review and blocked "
            "cases first."
        ),
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
        help="Filter by the current pipeline status.",
    )

    signal = filters[1].selectbox(
        "Signal",
        [
            "All",
            *options["signals"],
        ],
        key="overview_signal",
        help="Filter by downstream evidence signal.",
    )

    label = filters[2].selectbox(
        "Label",
        [
            "All",
            "Unreviewed",
            *options["labels"],
        ],
        key="overview_label",
        help="Filter by the current case label.",
    )

    repository = filters[3].selectbox(
        "Repository",
        [
            "All",
            *options["repositories"],
        ],
        key="overview_repository",
        help="Restrict results to one repository.",
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
        str(settings.db_path),
        search,
        stage,
        signal,
        label,
        repository,
        sort,
    )
