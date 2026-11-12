#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import streamlit as st

from ui.parquet_store import (
    ParquetBackendError,
    ParquetStore,
    cached_query,
    clear_parquet_caches,
    get_parquet_store,
)


def _fmt_int(value: Any) -> str:
    try:
        return f"{int(value or 0):,}"
    except Exception:
        return "0"


def _safe_text(value: Any) -> str:
    return "" if value is None else str(value)


def _option_values(column: str) -> list[str]:
    allowed = {"case_status", "final_label", "repo_language", "ai_cohort", "primary_region"}
    if column not in allowed:
        raise ValueError(f"Unsupported filter column: {column}")
    frame = cached_query(
        f"""
        SELECT DISTINCT coalesce(CAST({column} AS VARCHAR), '(none)') AS value
        FROM pq_cases
        ORDER BY value
        """
    )
    return [str(value) for value in frame["value"].tolist()]


def render_parquet_overview(store: ParquetStore) -> None:
    st.subheader("Research snapshot overview")
    st.caption(
        "Hugging Face Parquet → local HF cache → DuckDB. "
        "The dashboard queries local cached Parquet; large evidence payloads remain lazy/on-demand."
    )

    overview_df = cached_query("SELECT * FROM pq_summary_overview")
    if overview_df.empty:
        st.info("No overview rows are available in the Parquet snapshot.")
        return

    row = overview_df.iloc[0].to_dict()
    cols = st.columns(6)
    cols[0].metric("Cases", _fmt_int(row.get("total_cases")))
    cols[1].metric("Repositories", _fmt_int(row.get("total_repositories")))
    cols[2].metric("Findings", _fmt_int(row.get("total_findings")))
    cols[3].metric("Introduced", _fmt_int(row.get("introduced_findings")))
    cols[4].metric("High / critical", _fmt_int((row.get("high_findings") or 0) + (row.get("critical_findings") or 0)))
    cols[5].metric("Labelled", _fmt_int(row.get("labelled_cases")))

    if int(row.get("region_profiled_cases") or 0) == 0:
        st.warning(
            "This snapshot currently has no populated primary-region profiles in case_index. "
            "Region charts therefore cannot yet provide meaningful coverage analysis."
        )

    left, right = st.columns([1, 1])

    with left:
        st.markdown("#### Finding types")
        findings = cached_query(
            """
            SELECT finding_type, SUM(finding_count) AS findings
            FROM pq_summary_findings
            GROUP BY finding_type
            ORDER BY findings DESC
            LIMIT 20
            """
        )
        if not findings.empty:
            st.bar_chart(findings.set_index("finding_type"))
        else:
            st.info("No scanner findings in this snapshot.")

    with right:
        st.markdown("#### Top repositories by findings")
        repos = cached_query(
            """
            SELECT repo_full_name, finding_count, case_count
            FROM pq_summary_repos
            ORDER BY finding_count DESC, case_count DESC
            LIMIT 20
            """
        )
        if not repos.empty:
            st.dataframe(repos, hide_index=True, width="stretch")

    st.markdown("#### Timeline")
    timeline = cached_query(
        """
        SELECT month, case_count, finding_count, introduced_finding_count
        FROM pq_summary_timeline
        ORDER BY month
        """
    )
    if not timeline.empty:
        chart = timeline.set_index("month")[["case_count", "finding_count", "introduced_finding_count"]]
        st.line_chart(chart)

    st.markdown("#### Case labels / states")
    case_summary = cached_query(
        """
        SELECT case_status, final_label, ai_cohort, case_count, finding_count
        FROM pq_summary_cases
        ORDER BY case_count DESC
        """
    )
    st.dataframe(case_summary, hide_index=True, width="stretch")


def _build_case_query(
    status: str,
    label: str,
    language: str,
    search: str,
    introduced_only: bool,
) -> tuple[str, list[Any]]:
    where = ["1=1"]
    params: list[Any] = []

    for column, value in (
        ("case_status", status),
        ("final_label", label),
        ("repo_language", language),
    ):
        if value != "All":
            if value == "(none)":
                where.append(f"{column} IS NULL")
            else:
                where.append(f"{column} = ?")
                params.append(value)

    if search.strip():
        token = f"%{search.strip().lower()}%"
        where.append(
            "(" 
            "lower(coalesce(repo_full_name, '')) LIKE ? OR "
            "lower(coalesce(issue_title, '')) LIKE ? OR "
            "lower(coalesce(issue_author, '')) LIKE ? OR "
            "CAST(issue_number AS VARCHAR) = ? OR "
            "CAST(case_id AS VARCHAR) = ?"
            ")"
        )
        params.extend([token, token, token, search.strip(), search.strip()])

    if introduced_only:
        where.append("introduced_finding_count > 0")

    return " AND ".join(where), params


def render_parquet_case_review(store: ParquetStore) -> None:
    st.subheader("Case review")
    st.caption(
        "Fast read-only review over the immutable Parquet snapshot. "
        "Manual labels/tags are not written back to Hugging Face."
    )

    statuses = ["All"] + _option_values("case_status")
    labels = ["All"] + _option_values("final_label")
    languages = ["All"] + _option_values("repo_language")

    f1, f2, f3, f4 = st.columns([1.1, 1.1, 1.1, 1.7])
    with f1:
        status = st.selectbox("Status", statuses, key="pq_status")
    with f2:
        label = st.selectbox("Final label", labels, key="pq_label")
    with f3:
        language = st.selectbox("Language", languages, key="pq_language")
    with f4:
        search = st.text_input("Search repo / issue / case ID", key="pq_search")

    introduced_only = st.checkbox("Introduced findings only", value=False, key="pq_introduced")

    where_sql, params = _build_case_query(status, label, language, search, introduced_only)
    count_row = store.one(f"SELECT COUNT(*) AS n FROM pq_cases WHERE {where_sql}", params) or {"n": 0}
    total = int(count_row.get("n") or 0)

    page_size = 100
    max_page = max(1, (total + page_size - 1) // page_size)
    current_page = min(max(int(st.session_state.get("pq_page", 1)), 1), max_page)
    st.session_state["pq_page"] = current_page
    page = int(
        st.number_input(
            "Page",
            min_value=1,
            max_value=max_page,
            step=1,
            key="pq_page",
        )
    )
    offset = (page - 1) * page_size

    rows = store.query_df(
        f"""
        SELECT
            case_id,
            repo_full_name,
            repo_stars,
            repo_language,
            issue_number,
            issue_title,
            case_status,
            final_label,
            ai_cohort,
            primary_region,
            finding_count,
            introduced_finding_count,
            critical_finding_count,
            high_finding_count
        FROM pq_cases
        WHERE {where_sql}
        ORDER BY introduced_finding_count DESC, finding_count DESC, repo_stars DESC, case_id
        LIMIT {page_size} OFFSET {offset}
        """,
        params,
    )

    st.caption(f"{total:,} matching cases · page {page:,} of {max_page:,}")
    if rows.empty:
        st.info("No cases match these filters.")
        return

    st.dataframe(rows, hide_index=True, width="stretch", height=360)

    options = rows.to_dict("records")
    selected = st.selectbox(
        "Open case",
        options,
        format_func=lambda item: (
            f"#{int(item['case_id'])} · {item.get('repo_full_name')} · "
            f"issue #{item.get('issue_number')} · {item.get('issue_title') or ''}"
        ),
        key="pq_selected_case",
    )
    case_id = int(selected["case_id"])
    _render_case_detail(store, case_id)


def _render_case_detail(store: ParquetStore, case_id: int) -> None:
    case = store.one("SELECT * FROM pq_cases WHERE case_id = ? LIMIT 1", [case_id])
    if not case:
        st.warning("Case not found in case_index.parquet.")
        return

    detail = store.one("SELECT * FROM pq_case_detail WHERE case_id = ? LIMIT 1", [case_id]) or {}

    st.markdown("---")
    st.markdown(f"### Case #{case_id} · {_safe_text(case.get('repo_full_name'))}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Findings", _fmt_int(case.get("finding_count")))
    c2.metric("Introduced", _fmt_int(case.get("introduced_finding_count")))
    c3.metric("High", _fmt_int(case.get("high_finding_count")))
    c4.metric("Critical", _fmt_int(case.get("critical_finding_count")))
    c5.metric("AI markers", _fmt_int(case.get("ai_marker_count")))

    link_a, link_b = st.columns(2)
    with link_a:
        if case.get("issue_url"):
            st.link_button("Open GitHub issue", str(case["issue_url"]), width="stretch")
    with link_b:
        if case.get("pr_url"):
            st.link_button("Open pull request", str(case["pr_url"]), width="stretch")

    st.markdown(f"**Issue:** {_safe_text(case.get('issue_title'))}")
    st.caption(
        f"Status: {_safe_text(case.get('case_status')) or '(none)'} · "
        f"Final label: {_safe_text(case.get('final_label')) or '(none)'} · "
        f"AI cohort: {_safe_text(case.get('ai_cohort')) or '(none)'} · "
        f"Region: {_safe_text(case.get('primary_region')) or '(none)'}"
    )

    with st.expander("Issue body", expanded=False):
        st.markdown(_safe_text(detail.get("issue_body")) or "_No issue body stored._")
    with st.expander("Pull-request body", expanded=False):
        st.markdown(_safe_text(detail.get("pr_body")) or "_No PR body stored._")
    with st.expander("Review notes / structured features", expanded=False):
        if detail.get("review_notes"):
            st.markdown(_safe_text(detail.get("review_notes")))
        for key in ("region_counts_json", "scanner_routes_json", "language_json", "feature_json"):
            value = detail.get(key)
            if value:
                st.markdown(f"**{key}**")
                try:
                    st.json(json.loads(str(value)))
                except Exception:
                    st.code(str(value))

    markers = store.query_df(
        """
        SELECT marker_text, marker_location, confidence, matched_tool, created_at
        FROM pq_ai_markers
        WHERE case_id = ?
        ORDER BY marker_location, marker_text
        """,
        [case_id],
    )
    if not markers.empty:
        st.markdown("#### AI markers")
        st.dataframe(markers, hide_index=True, width="stretch")

    region_rows = store.query_df(
        """
        SELECT path, region, language, confidence, scanner_routes, evidence, mapping_version
        FROM pq_artifact_regions
        WHERE case_id = ?
        ORDER BY region, path
        """,
        [case_id],
    )
    if not region_rows.empty:
        st.markdown("#### Artifact regions")
        st.dataframe(region_rows, hide_index=True, width="stretch")

    findings = store.query_df(
        """
        SELECT
            finding_id, scanner, finding_type, severity, rule_id, cwe,
            file_path, line, introduced, description_preview
        FROM pq_findings
        WHERE case_id = ?
        ORDER BY introduced DESC, scanner, file_path, line, finding_id
        """,
        [case_id],
    )
    st.markdown("#### Scanner findings")
    if findings.empty:
        st.info("No findings stored for this case.")
    else:
        st.dataframe(findings, hide_index=True, width="stretch", height=280)
        finding_ids = [int(value) for value in findings["finding_id"].tolist()]
        selected_finding = st.selectbox(
            "Open finding evidence",
            finding_ids,
            key=f"pq_finding_{case_id}",
        )
        full = store.one(
            "SELECT * FROM pq_finding_detail WHERE finding_id = ? LIMIT 1",
            [int(selected_finding)],
        )
        if full:
            with st.expander("Full finding evidence", expanded=False):
                st.markdown("**Description**")
                st.code(_safe_text(full.get("description")) or "(none)", wrap_lines=True)
                st.markdown("**Evidence**")
                st.code(_safe_text(full.get("evidence")) or "(none)", wrap_lines=True)
                st.markdown("**Raw JSON**")
                st.code(_safe_text(full.get("raw_json")) or "(none)", language="json", wrap_lines=True)

    files = store.query_df(
        """
        SELECT file_id, filename, status, additions, deletions, category, has_patch
        FROM pq_files
        WHERE pr_id = ?
        ORDER BY category, filename
        """,
        [int(case.get("pr_id"))],
    )
    st.markdown("#### Changed files")
    if files.empty:
        st.info("No changed files stored for this PR.")
    else:
        st.dataframe(files, hide_index=True, width="stretch", height=280)
        patchable = files[files["has_patch"] == True]  # noqa: E712
        if not patchable.empty:
            patch_options = patchable.to_dict("records")
            patch_choice = st.selectbox(
                "Patch file",
                patch_options,
                format_func=lambda item: f"{int(item['file_id'])} · {item['filename']}",
                key=f"pq_patch_choice_{case_id}",
            )
            if st.button(
                "Load patch",
                key=f"pq_load_patch_{case_id}_{int(patch_choice['file_id'])}",
                help="The first patch view may cache ~219 MB of patch Parquet shards locally. Later patch reads are local and fast.",
            ):
                with st.spinner("Caching patch shards on first use, then reading locally..."):
                    try:
                        patch = store.patch_detail(int(patch_choice["file_id"]))
                    except ParquetBackendError as exc:
                        st.error(str(exc))
                        patch = None
                if patch and patch.get("patch"):
                    st.code(str(patch["patch"]), language="diff", wrap_lines=False)
                else:
                    st.info("No patch payload was found for this file.")

    notes = store.query_df(
        """
        SELECT note, created_at
        FROM pq_case_notes
        WHERE case_id = ?
        ORDER BY created_at
        """,
        [case_id],
    )
    if not notes.empty:
        st.markdown("#### Existing case notes")
        st.dataframe(notes, hide_index=True, width="stretch")


def render_parquet_scanner_insights(store: ParquetStore) -> None:
    st.subheader("Scanner insights")
    totals = store.one(
        """
        SELECT
            COUNT(*) AS findings,
            COUNT(*) FILTER (WHERE introduced) AS introduced,
            COUNT(DISTINCT case_id) AS cases,
            COUNT(DISTINCT repo_id) AS repos
        FROM pq_findings
        """
    ) or {}

    cols = st.columns(4)
    cols[0].metric("Findings", _fmt_int(totals.get("findings")))
    cols[1].metric("Introduced", _fmt_int(totals.get("introduced")))
    cols[2].metric("Cases", _fmt_int(totals.get("cases")))
    cols[3].metric("Repositories", _fmt_int(totals.get("repos")))

    left, right = st.columns(2)
    with left:
        by_scanner = cached_query(
            """
            SELECT scanner, COUNT(*) AS findings,
                   COUNT(*) FILTER (WHERE introduced) AS introduced
            FROM pq_findings
            GROUP BY scanner
            ORDER BY findings DESC
            """
        )
        st.markdown("#### Findings by scanner")
        st.dataframe(by_scanner, hide_index=True, width="stretch")

    with right:
        by_type = cached_query(
            """
            SELECT finding_type, severity, COUNT(*) AS findings,
                   COUNT(*) FILTER (WHERE introduced) AS introduced
            FROM pq_findings
            GROUP BY finding_type, severity
            ORDER BY findings DESC
            """
        )
        st.markdown("#### Finding type / severity")
        st.dataframe(by_type, hide_index=True, width="stretch")

    st.markdown("#### Highest-yield cases")
    top_cases = cached_query(
        """
        SELECT
            case_id, repo_full_name, issue_number, issue_title,
            finding_count, introduced_finding_count,
            critical_finding_count, high_finding_count
        FROM pq_cases
        WHERE finding_count > 0
        ORDER BY introduced_finding_count DESC, finding_count DESC
        LIMIT 100
        """
    )
    st.dataframe(top_cases, hide_index=True, width="stretch")


def render_parquet_pattern_insights(store: ParquetStore) -> None:
    st.subheader("Pattern insights")
    left, right = st.columns(2)

    with left:
        cohorts = cached_query(
            """
            SELECT
                coalesce(ai_cohort, '(none)') AS ai_cohort,
                COUNT(*) AS cases,
                SUM(finding_count) AS findings,
                SUM(introduced_finding_count) AS introduced
            FROM pq_cases
            GROUP BY ai_cohort
            ORDER BY cases DESC
            """
        )
        st.markdown("#### AI cohort")
        st.dataframe(cohorts, hide_index=True, width="stretch")

    with right:
        labels = cached_query(
            """
            SELECT
                coalesce(final_label, '(none)') AS final_label,
                COUNT(*) AS cases,
                SUM(finding_count) AS findings,
                SUM(introduced_finding_count) AS introduced
            FROM pq_cases
            GROUP BY final_label
            ORDER BY cases DESC
            """
        )
        st.markdown("#### Final labels")
        st.dataframe(labels, hide_index=True, width="stretch")

    regions = cached_query(
        """
        SELECT
            coalesce(primary_region, '(none)') AS primary_region,
            COUNT(*) AS cases,
            SUM(finding_count) AS findings,
            SUM(introduced_finding_count) AS introduced
        FROM pq_cases
        GROUP BY primary_region
        ORDER BY cases DESC
        """
    )
    st.markdown("#### Region coverage")
    st.dataframe(regions, hide_index=True, width="stretch")
    if len(regions) == 1 and str(regions.iloc[0]["primary_region"]) == "(none)":
        st.warning(
            "All cases in this Parquet snapshot currently have primary_region=NULL. "
            "Region-yield conclusions should not be drawn from this snapshot yet."
        )

    st.markdown("#### Repository concentration")
    repos = cached_query(
        """
        SELECT repo_full_name, repo_stars, repo_language,
               COUNT(*) AS cases,
               SUM(finding_count) AS findings,
               SUM(introduced_finding_count) AS introduced
        FROM pq_cases
        GROUP BY repo_full_name, repo_stars, repo_language
        ORDER BY findings DESC, cases DESC
        LIMIT 100
        """
    )
    st.dataframe(repos, hide_index=True, width="stretch")


def render_parquet_excluded_cases(store: ParquetStore) -> None:
    st.subheader("Excluded cases")
    st.caption(
        "The 6 GB detail payload stays remote. A 6 KB routing index selects the one Parquet shard that can contain the requested ID."
    )

    reasons = store.query_df(
        """
        SELECT reason, COUNT(*) AS cases
        FROM pq_excluded
        GROUP BY reason
        ORDER BY cases DESC
        """
    )
    st.dataframe(reasons, hide_index=True, width="stretch", height=240)

    search = st.text_input("Search excluded repo / ID", key="pq_excluded_search")
    where = "1=1"
    params: list[Any] = []
    if search.strip():
        token = f"%{search.strip().lower()}%"
        where = "(lower(coalesce(repo, '')) LIKE ? OR CAST(excluded_case_id AS VARCHAR) = ?)"
        params = [token, search.strip()]

    rows = store.query_df(
        f"""
        SELECT excluded_case_id, repo, issue_number, pr_number, reason, details_preview
        FROM pq_excluded
        WHERE {where}
        ORDER BY excluded_case_id DESC
        LIMIT 200
        """,
        params,
    )
    st.dataframe(rows, hide_index=True, width="stretch", height=360)
    if rows.empty:
        return

    options = rows.to_dict("records")
    selected = st.selectbox(
        "Open excluded case",
        options,
        format_func=lambda item: f"#{int(item['excluded_case_id'])} · {item.get('repo')} · {item.get('reason')}",
        key="pq_excluded_selected",
    )
    excluded_id = int(selected["excluded_case_id"])

    if st.button("Load full excluded-case detail", key=f"pq_excluded_load_{excluded_id}"):
        routes = store.excluded_route(excluded_id)
        st.caption(f"Routing index selected {len(routes)} remote shard(s): {', '.join(routes) or '(none)'}")
        with st.spinner("Reading the routed remote Parquet shard..."):
            detail = store.excluded_detail(excluded_id)
        if not detail:
            st.warning("No detail row found.")
            return
        st.markdown("**Details**")
        st.code(_safe_text(detail.get("details")) or "(none)", wrap_lines=True)
        st.markdown("**Changed files JSON**")
        st.code(_safe_text(detail.get("changed_files_json")) or "(none)", language="json", wrap_lines=True)


def render_parquet_settings(store: ParquetStore) -> None:
    st.subheader("Parquet data settings")
    st.json(
        {
            "backend": "Hugging Face Parquet + local HF cache + DuckDB",
            "dataset_repo": store.repo_id,
            "revision": store.revision,
            "snapshot_root": str(store.snapshot_root),
            "hot_cache_mb": round(store.hot_cache_size_bytes / 1024**2, 2),
            "large_remote_payloads": [
                "parquet/v1/ui/excluded_case_detail/*.parquet",
                "parquet/v1/ui/file_patch/*.parquet (lazy local cache on first patch view)",
            ],
            "write_mode": "read-only snapshot",
        }
    )

    st.markdown("#### Cached hot files")
    st.dataframe(pd.DataFrame(store.hot_cache_rows()), hide_index=True, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Clear query-result cache", width="stretch"):
            clear_parquet_caches()
            st.success("Query-result cache cleared. The HF file cache was left intact.")
    with c2:
        if st.button("Reload latest HF snapshot", width="stretch"):
            clear_parquet_caches()
            get_parquet_store.clear()
            st.rerun()
