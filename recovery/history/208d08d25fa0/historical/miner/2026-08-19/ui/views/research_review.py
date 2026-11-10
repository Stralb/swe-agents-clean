#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import os
from collections import Counter
from typing import Any

import pandas as pd
import streamlit as st

from ui.parquet_store import ParquetBackendError, ParquetStore
from ui.research_layer import ResearchLayer
from ui.review_store import (
    BENIGN_EXPLANATION_LABELS,
    CONFIDENCE_LABELS,
    DISGUISE_LABELS,
    GOAL_EFFECT_LABELS,
    INTENT_LABELS,
    ISSUE_CONNECTION_LABELS,
    MALICIOUSNESS_LABELS,
    REVIEW_STATUSES,
    ReviewStore,
)

_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
_ALIGNMENT_ORDER = {"High": 0, "Medium": 1, "Low": 2, "None": 3}


def _fmt(value: Any) -> str:
    try:
        return f"{int(float(value or 0)):,}"
    except Exception:
        return "0"


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value)


def _fmt_hours(value: Any) -> str:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if hours < 0:
        return f"{hours:.1f} h"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24.0:.1f} days"


def _select_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def _normalise_path(value: Any) -> str:
    path = _text(value).strip().replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def _split_paths(value: Any) -> list[str]:
    output: list[str] = []
    for item in _text(value).split(","):
        path = _normalise_path(item)
        if path and not path.startswith("+") and path not in output:
            output.append(path)
    return output


def _review_frame(layer: ResearchLayer, reviews: ReviewStore) -> pd.DataFrame:
    queue = layer.case_summary.copy()
    labels = reviews.frame()
    defaults = {
        "review_status": "Unreviewed",
        "maliciousness": "Unreviewed",
        "intent": "Unassigned",
        "disguise": "Unassigned",
        "confidence": "Unassigned",
        "issue_change_connection": "Unassigned",
        "goal_effect_relationship": "Unassigned",
        "benign_explanation": "Unassigned",
        "rationale": "",
        "technical_notes": "",
        "reviewer": "",
        "updated_at": "",
    }
    if labels.empty:
        for column, default in defaults.items():
            queue[column] = default
        return queue

    keep = ["case_id"] + [column for column in defaults if column in labels.columns]
    queue = queue.merge(labels[keep], how="left", on="case_id")
    for column, default in defaults.items():
        if column not in queue.columns:
            queue[column] = default
        else:
            queue[column] = queue[column].fillna(default)
    return queue


def _progress_metrics(layer: ResearchLayer, reviews: ReviewStore) -> None:
    ids = [int(value) for value in layer.case_summary["case_id"].tolist()]
    progress = reviews.progress(ids)
    columns = st.columns(6)
    columns[0].metric("Static-analysis positives", _fmt(progress["total"]))
    columns[1].metric("Reviewed", _fmt(progress["reviewed"]))
    columns[2].metric("In review", _fmt(progress["in_review"]))
    columns[3].metric("Suspicious / malicious", _fmt(progress["suspicious_or_malicious"]))
    columns[4].metric("Benign", _fmt(progress["benign"]))
    columns[5].metric("Scanner / attribution artifact", _fmt(progress["artifact"]))

    total = max(1, progress["total"])
    st.progress(
        progress["reviewed"] / total,
        text=f"Manual validation progress: {progress['reviewed']}/{progress['total']} cases",
    )


def _upstream_csv(layer: ResearchLayer) -> bytes:
    return layer.upstream_export().to_csv(index=False).encode("utf-8")


def render_study_overview(
    layer: ResearchLayer,
    reviews: ReviewStore,
) -> None:
    st.title("Potentially malicious issue study")
    st.caption(
        "Current focus: the static-analysis-positive cohort. The interface separates upstream issue evidence, "
        "downstream code/scanner evidence, and the final human decision."
    )

    stats = layer.stats
    review_progress = reviews.progress(
        [int(value) for value in layer.case_summary["case_id"].tolist()]
    )

    st.markdown("### Research funnel")
    columns = st.columns(5)
    columns[0].metric("Included candidates", _fmt(stats.total_cases))
    columns[1].metric("Static-analysis positives", _fmt(stats.positive_cases))
    columns[2].metric("Raw introduced findings", _fmt(stats.introduced_findings))
    columns[3].metric("Canonical security events", _fmt(stats.unique_events))
    columns[4].metric("Manually reviewed", _fmt(review_progress["reviewed"]))

    positive_pct = (100.0 * stats.positive_cases / stats.total_cases) if stats.total_cases else 0.0
    st.info(
        f"The automated pipeline narrowed {stats.total_cases:,} linked issue/PR candidates to "
        f"{stats.positive_cases:,} cases with introduced static-analysis findings ({positive_pct:.1f}%). "
        "These are the cases to inspect manually."
    )

    _progress_metrics(layer, reviews)

    left, right = st.columns(2)
    with left:
        st.markdown("### What the issue says about the downstream change")
        alignment = (
            layer.case_summary.groupby("issue_change_alignment", as_index=False)
            .agg(cases=("case_id", "count"))
        )
        alignment["order"] = alignment["issue_change_alignment"].map(_ALIGNMENT_ORDER).fillna(9)
        st.dataframe(
            alignment.sort_values("order").drop(columns=["order"]),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "This is deterministic overlap only: exact affected package/version/file/vulnerability mentions, "
            "plus coarse issue-language alignment with the downstream event family. It is not a maliciousness score."
        )

    with right:
        st.markdown("### Downstream evidence families")
        archetypes = (
            layer.case_summary.groupby("archetype", as_index=False)
            .agg(
                cases=("case_id", "count"),
                unique_events=("unique_event_count", "sum"),
                raw_findings=("raw_finding_count", "sum"),
            )
            .sort_values("cases", ascending=False)
        )
        st.dataframe(archetypes, hide_index=True, width="stretch")

    st.markdown("### What you need for the supervisor demo")
    st.write(
        "For each positive case you can now show: (1) the original issue request and deterministic upstream cues, "
        "(2) the exact introduced static-analysis event, changed files, scanner flags and patch, and "
        "(3) your manual judgement. Account age and author-history enrichment are optional later work, not a blocker."
    )

    d1, d2 = st.columns(2)
    d1.download_button(
        "Download 138-case upstream findings CSV",
        _upstream_csv(layer),
        file_name="upstream_findings_static_analysis_positive_cases.csv",
        mime="text/csv",
        width="stretch",
    )
    d2.download_button(
        "Download manual labels CSV",
        reviews.export_csv_bytes(),
        file_name="manual_issue_review_labels.csv",
        mime="text/csv",
        width="stretch",
    )


def _filter_queue(
    queue: pd.DataFrame,
    status: str,
    maliciousness: str,
    priority: str,
    archetype: str,
    alignment: str,
    search: str,
) -> pd.DataFrame:
    filtered = queue.copy()
    if status != "All":
        filtered = filtered[filtered["review_status"] == status]
    if maliciousness != "All":
        filtered = filtered[filtered["maliciousness"] == maliciousness]
    if priority != "All":
        filtered = filtered[filtered["review_priority"] == priority]
    if archetype != "All":
        filtered = filtered[filtered["archetype"] == archetype]
    if alignment != "All":
        filtered = filtered[filtered["issue_change_alignment"] == alignment]

    token = search.strip().lower()
    if token:
        mask = (
            filtered["repo_full_name"].fillna("").str.lower().str.contains(token, regex=False)
            | filtered["issue_title"].fillna("").str.lower().str.contains(token, regex=False)
            | filtered["issue_author"].fillna("").str.lower().str.contains(token, regex=False)
            | filtered["case_id"].astype(str).eq(token)
            | filtered["issue_number"].astype(str).eq(token)
        )
        filtered = filtered[mask]

    filtered["_priority"] = filtered["review_priority"].map(_PRIORITY_ORDER).fillna(3)
    filtered["_alignment"] = filtered["issue_change_alignment"].map(_ALIGNMENT_ORDER).fillna(4)
    filtered = filtered.sort_values(
        ["_priority", "_alignment", "review_status", "unique_event_count", "case_id"],
        ascending=[True, True, True, True, True],
    ).drop(columns=["_priority", "_alignment"])
    return filtered.reset_index(drop=True)


def _queue_screen(
    layer: ResearchLayer,
    reviews: ReviewStore,
) -> None:
    st.title("Manual review queue")
    st.caption(
        f"{layer.stats.positive_cases:,} cases have introduced static-analysis findings. "
        "Open a case to move through Upstream -> Downstream -> Decision."
    )
    _progress_metrics(layer, reviews)

    queue = _review_frame(layer, reviews)
    archetypes = ["All"] + sorted(queue["archetype"].dropna().unique().tolist())

    f1, f2, f3 = st.columns(3)
    with f1:
        status = st.selectbox("Review status", ["All"] + REVIEW_STATUSES, key="rq_status")
    with f2:
        maliciousness = st.selectbox("Manual label", ["All"] + MALICIOUSNESS_LABELS, key="rq_maliciousness")
    with f3:
        search = st.text_input("Search repo / issue / author / case", key="rq_search")

    f4, f5, f6 = st.columns(3)
    with f4:
        priority = st.selectbox("Review priority", ["All", "High", "Medium", "Low"], key="rq_priority")
    with f5:
        archetype = st.selectbox("Downstream family", archetypes, key="rq_archetype")
    with f6:
        alignment = st.selectbox(
            "Issue -> change overlap",
            ["All", "High", "Medium", "Low", "None"],
            key="rq_alignment",
        )

    filtered = _filter_queue(
        queue,
        status,
        maliciousness,
        priority,
        archetype,
        alignment,
        search,
    )
    st.session_state["rq_case_ids"] = [int(value) for value in filtered["case_id"].tolist()]

    toolbar_left, toolbar_right = st.columns([3, 1.5])
    toolbar_left.caption(
        f"{len(filtered):,} matching cases. Issue -> change overlap is for triage only; inspect the actual issue and diff before deciding."
    )
    toolbar_right.download_button(
        "Download upstream CSV",
        _upstream_csv(layer),
        file_name="upstream_findings_static_analysis_positive_cases.csv",
        mime="text/csv",
        width="stretch",
    )

    page_size = 20
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page = min(max(int(st.session_state.get("rq_page", 1)), 1), total_pages)
    st.session_state["rq_page"] = page

    top_left, top_mid, top_right = st.columns([1, 2, 1])
    if top_left.button("<- Previous page", disabled=page <= 1, width="stretch"):
        st.session_state["rq_page"] = page - 1
        st.rerun()
    top_mid.caption(f"Page {page}/{total_pages}")
    if top_right.button("Next page ->", disabled=page >= total_pages, width="stretch"):
        st.session_state["rq_page"] = page + 1
        st.rerun()

    start = (page - 1) * page_size
    page_rows = filtered.iloc[start : start + page_size]
    if page_rows.empty:
        st.info("No cases match the current filters.")
        return

    for row in page_rows.to_dict("records"):
        case_id = int(row["case_id"])
        with st.container(border=True):
            main, upstream, downstream, action = st.columns([3.1, 2.1, 1.8, 1.05])
            with main:
                st.markdown(
                    f"**#{case_id} · {_text(row.get('repo_full_name'))}**  \n"
                    f"Issue #{_text(row.get('issue_number'))}: {_text(row.get('issue_title'))}"
                )
                st.caption(
                    f"Issue author: {_text(row.get('issue_author')) or 'unknown'} · "
                    f"PR author: {_text(row.get('pr_author')) or 'unknown'} · "
                    f"PR +{_fmt(row.get('pr_additions'))}/-{_fmt(row.get('pr_deletions'))} in "
                    f"{_fmt(row.get('changed_files_count'))} files"
                )
            with upstream:
                st.markdown(f"**Upstream overlap: {_text(row.get('issue_change_alignment'))}**")
                st.caption(_text(row.get("upstream_summary")))
                if _text(row.get("review_cues")):
                    st.caption(f"Review cues: {_text(row.get('review_cues'))}")
            with downstream:
                st.markdown(f"**{_text(row.get('archetype'))}**")
                st.write(
                    f"{_fmt(row.get('unique_event_count'))} canonical events · "
                    f"{_fmt(row.get('raw_finding_count'))} raw flags"
                )
                st.caption(
                    f"Attribution: {_text(row.get('strongest_attribution')).title()} · "
                    f"Priority: {_text(row.get('review_priority'))}"
                )
            with action:
                st.caption(f"Label: {_text(row.get('maliciousness')) or 'Unreviewed'}")
                if st.button("Inspect ->", key=f"rq_open_{case_id}", width="stretch", type="primary"):
                    st.session_state["rq_selected_case"] = case_id
                    st.session_state[f"rq_workspace_{case_id}"] = "Upstream"
                    st.rerun()


def _next_case_id(current: int) -> int | None:
    ids = [int(value) for value in st.session_state.get("rq_case_ids", [])]
    if current not in ids:
        return None
    index = ids.index(current)
    if index + 1 >= len(ids):
        return None
    return ids[index + 1]


def _event_heading(event: dict[str, Any]) -> str:
    family = _text(event.get("event_family"))
    severity = _text(event.get("severity")).upper() or "UNKNOWN"
    identifier = _text(event.get("canonical_vuln_id") or event.get("rule_id"))
    title = _text(event.get("title"))
    suffix = identifier or title[:90]
    return f"{family} · {severity}" + (f" · {suffix}" if suffix else "")


def _render_event(event: dict[str, Any], attribution: pd.DataFrame, expanded: bool = False) -> None:
    with st.expander(_event_heading(event), expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attribution", _text(event.get("attribution_strength")).title())
        c2.metric("Raw scanner records", _fmt(event.get("raw_finding_count")))
        c3.metric("Scanners", _fmt(event.get("scanner_count")))
        c4.metric("Context", _text(event.get("primary_context")) or "unknown")

        family = _text(event.get("event_family"))
        if family.startswith("Dependency"):
            st.markdown(f"**Package:** `{_text(event.get('package')) or '(unknown)'}`")
            old_version = _text(event.get("old_version"))
            new_version = _text(event.get("new_version"))
            version = _text(event.get("version"))
            if old_version or new_version:
                st.markdown(f"**Version change:** `{old_version or '?'} -> {new_version or '?'}`")
            elif version:
                st.markdown(f"**Affected version:** `{version}`")
            if event.get("canonical_vuln_id"):
                st.markdown(f"**Vulnerability:** `{_text(event.get('canonical_vuln_id'))}`")
            if event.get("fixed_version"):
                st.markdown(f"**Known fixed version:** `{_text(event.get('fixed_version'))}`")

        st.markdown("**Why this is linked to the PR**")
        st.write(_text(event.get("attribution_reason")))
        if event.get("codeflow_changed_paths"):
            st.markdown("**PR-changed path(s) in CodeQL flow**")
            st.code(_text(event.get("codeflow_changed_paths")), wrap_lines=True)

        st.markdown("**Scanner explanation**")
        st.write(_text(event.get("title")) or "No description available.")
        st.caption(
            f"Scanner(s): {_text(event.get('scanners'))} · Primary file(s): {_text(event.get('primary_files'))}"
        )

        ids = {
            int(value)
            for value in _text(event.get("raw_finding_ids")).split(",")
            if value.strip().isdigit()
        }
        raw = attribution[attribution["finding_id"].isin(ids)].copy()
        if not raw.empty:
            display = raw[
                [
                    "finding_id",
                    "scanner",
                    "rule_id",
                    "file_path",
                    "line",
                    "effective_severity",
                    "primary_file_changed",
                    "codeflow_hits_changed_file",
                    "description_preview",
                ]
            ]
            st.dataframe(display, hide_index=True, width="stretch")


def _render_upstream_tab(
    layer: ResearchLayer,
    store: ParquetStore,
    case: dict[str, Any],
    case_id: int,
) -> None:
    upstream = layer.case_upstream(case_id)
    detail = store.one("SELECT * FROM pq_case_detail WHERE case_id = ? LIMIT 1", [case_id]) or {}

    st.markdown("### 1. Original issue request")
    st.markdown(f"**{_text(case.get('issue_title'))}**")
    with st.container(border=True):
        st.markdown(_text(detail.get("issue_body")) or "_No issue body stored._")

    st.markdown("### 2. What in the issue overlaps with the downstream change?")
    alignment = _text(upstream.get("issue_change_alignment")) or "None"
    st.info(f"Deterministic issue -> change overlap: **{alignment}**. {_text(upstream.get('upstream_summary'))}")

    overlap_rows = []
    for label, key in (
        ("Affected package(s) named in issue", "matched_packages"),
        ("Affected version(s) named in issue", "matched_versions"),
        ("Changed/finding file(s) named in issue", "matched_files"),
        ("Vulnerability ID(s) named in issue", "matched_vulnerability_ids"),
    ):
        value = _text(upstream.get(key))
        if value:
            overlap_rows.append({"signal": label, "value": value})
    if overlap_rows:
        st.dataframe(pd.DataFrame(overlap_rows), hide_index=True, width="stretch")
    else:
        st.caption("No exact affected package/version/file/vulnerability identifier was found in the issue text.")

    cues1, cues2 = st.columns(2)
    with cues1:
        st.markdown("#### Technical issue cues")
        technical = _text(upstream.get("technical_cues"))
        st.write(technical or "No selected technical cue group matched.")
    with cues2:
        st.markdown("#### Review cues")
        review_cues = _text(upstream.get("review_cues"))
        if review_cues:
            st.warning(
                "Matched wording: " + review_cues + ". These words only prioritise reading; they do not establish malicious intent."
            )
        else:
            st.write("No selected risky-action phrase matched.")

    st.markdown("### 3. Existing author and PR context")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Issue author", _text(case.get("issue_author")) or "unknown")
    c2.metric("PR author", _text(case.get("pr_author")) or "unknown")
    c3.metric("Same author", "Yes" if upstream.get("same_issue_pr_author") else "No")
    c4.metric("Issue -> PR", _fmt_hours(upstream.get("issue_to_pr_hours")))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Issue comments", _fmt(upstream.get("issue_comments_count")))
    c6.metric("Changed lines", _fmt((case.get("pr_additions") or 0) + (case.get("pr_deletions") or 0)))
    c7.metric("Changed files", _fmt(case.get("changed_files_count")))
    c8.metric("PR merged", "Yes" if bool(case.get("pr_merged")) else "No")

    framing = _text(upstream.get("framing_cues"))
    if framing:
        st.caption(f"Issue framing words present: {framing}")

    with st.expander("Candidate-selection context", expanded=False):
        st.caption(
            "These fields explain why the issue entered the upstream candidate funnel. Since they are common by construction, "
            "they are kept out of the main decision surface."
        )
        feature_columns = [
            "has_code_block",
            "has_inline_code",
            "has_traceback_or_log",
            "has_file_path",
            "has_function_or_class",
            "has_dependency_or_version",
            "has_suggested_fix",
            "has_ai_marker",
            "ai_marker_count",
            "ai_cohort",
        ]
        st.json({column: case.get(column) for column in feature_columns})

        markers = store.query_df(
            """
            SELECT marker_text, marker_location, confidence, matched_tool
            FROM pq_ai_markers
            WHERE case_id = ?
            ORDER BY marker_location, marker_text
            """,
            [case_id],
        )
        if not markers.empty:
            st.dataframe(markers, hide_index=True, width="stretch")

    st.caption(
        "Not currently stored: GitHub account age, author-association/history, prior PR merge rate, and maintainer review text. "
        "Those can be enriched later if useful; they are not required for the current 138-case upstream summary."
    )


def _file_relation_rows(attribution: pd.DataFrame, filename: str) -> pd.DataFrame:
    normalized = _normalise_path(filename)
    rows: list[dict[str, Any]] = []
    for record in attribution.to_dict("records"):
        primary = _normalise_path(record.get("file_path"))
        flow_paths = _split_paths(record.get("codeflow_changed_paths"))
        relation = ""
        if primary == normalized:
            relation = "Primary scanner finding file"
        elif normalized in flow_paths:
            relation = "PR-changed file in CodeQL flow"
        if relation:
            row = dict(record)
            row["file_relationship"] = relation
            rows.append(row)
    return pd.DataFrame(rows)


def _render_downstream_tab(
    layer: ResearchLayer,
    store: ParquetStore,
    case: dict[str, Any],
    summary: dict[str, Any],
    events: pd.DataFrame,
    attribution: pd.DataFrame,
    case_id: int,
) -> None:
    st.markdown("### Why static analysis flagged this case")
    st.info(_text(summary.get("why_flagged")))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Canonical events", _fmt(summary.get("unique_event_count")))
    c2.metric("Raw scanner flags", _fmt(summary.get("raw_finding_count")))
    c3.metric("Collapsed duplicates", _fmt(summary.get("duplicate_report_count")))
    c4.metric("Strongly attributed", _fmt(summary.get("strong_attribution_events")))

    if int(summary.get("test_context_events") or 0) > 0:
        st.warning(
            f"{_fmt(summary.get('test_context_events'))} canonical event(s) are in tests, fixtures or mocks. "
            "Keep them visible, but interpret them separately from production-source findings."
        )
    if int(summary.get("lockfile_events") or 0) >= 20:
        st.warning(
            "Bulk dependency/lockfile case: scanner overlap and lockfile regeneration can inflate raw counts. "
            "Use canonical events and inspect the actual dependency change."
        )

    st.markdown("### Canonical introduced security events")
    for index, event in enumerate(events.to_dict("records")):
        _render_event(event, attribution, expanded=index == 0)

    st.markdown("### Changed-file evidence: diff + scanner flags")
    files = store.query_df(
        """
        SELECT file_id, filename, status, additions, deletions, category, has_patch
        FROM pq_files
        WHERE pr_id = ?
        ORDER BY filename
        """,
        [int(case.get("pr_id"))],
    )
    if files.empty:
        st.info("No changed-file metadata is available for this PR.")
        return

    rows: list[dict[str, Any]] = []
    for file_record in files.to_dict("records"):
        related = _file_relation_rows(attribution, _text(file_record.get("filename")))
        relations = []
        if not related.empty:
            relations = sorted(set(related["file_relationship"].astype(str).tolist()))
        row = dict(file_record)
        row["scanner_flags"] = len(related)
        row["static_analysis_relation"] = "; ".join(relations) if relations else "Changed file"
        rows.append(row)
    files_view = pd.DataFrame(rows).sort_values(
        ["scanner_flags", "additions", "filename"],
        ascending=[False, False, True],
    )

    st.dataframe(
        files_view[
            [
                "filename",
                "status",
                "additions",
                "deletions",
                "category",
                "scanner_flags",
                "static_analysis_relation",
            ]
        ],
        hide_index=True,
        width="stretch",
        height=300,
    )

    options = files_view.to_dict("records")
    selected_file = st.selectbox(
        "Inspect changed file",
        options,
        format_func=lambda item: (
            ("[FLAGGED] " if int(item.get("scanner_flags") or 0) else "")
            + f"{item.get('filename')} (+{_fmt(item.get('additions'))}/-{_fmt(item.get('deletions'))})"
        ),
        key=f"rq_downstream_file_{case_id}",
    )
    filename = _text(selected_file.get("filename"))
    related = _file_relation_rows(attribution, filename)

    st.markdown(f"#### Scanner flags connected to `{filename}`")
    if related.empty:
        st.caption("No scanner finding is directly reported on this file and no CodeQL flow maps through it.")
    else:
        columns = [
            "file_relationship",
            "finding_id",
            "scanner",
            "event_family",
            "rule_id",
            "effective_severity",
            "file_path",
            "line",
            "description_preview",
        ]
        st.dataframe(related[columns], hide_index=True, width="stretch", height=260)

    if bool(selected_file.get("has_patch")):
        if st.button(
            "Load diff for selected file",
            key=f"rq_patch_load_{case_id}_{int(selected_file['file_id'])}",
            type="primary",
        ):
            with st.spinner("Loading patch evidence..."):
                try:
                    patch = store.patch_detail(int(selected_file["file_id"]))
                except ParquetBackendError as exc:
                    st.error(str(exc))
                    patch = None
            if patch and patch.get("patch"):
                st.code(str(patch["patch"]), language="diff", wrap_lines=False)
            else:
                st.info("No patch payload was found for this file.")
    else:
        st.caption("No patch payload is stored for this file.")

    with st.expander("Raw scanner finding evidence / JSON", expanded=False):
        finding_ids = attribution["finding_id"].astype(int).tolist()
        if not finding_ids:
            st.info("No raw scanner rows are available.")
        else:
            selected_finding = st.selectbox(
                "Raw finding",
                finding_ids,
                key=f"rq_raw_finding_{case_id}",
            )
            full = store.one(
                "SELECT * FROM pq_finding_detail WHERE finding_id = ? LIMIT 1",
                [int(selected_finding)],
            )
            if full:
                st.markdown("**Description**")
                st.code(_text(full.get("description")) or "(none)", wrap_lines=True)
                st.markdown("**Evidence**")
                st.code(_text(full.get("evidence")) or "(none)", wrap_lines=True)
                st.markdown("**Raw JSON**")
                st.code(_text(full.get("raw_json")) or "(none)", language="json", wrap_lines=True)


def _manual_assessment_form(
    case_id: int,
    reviews: ReviewStore,
    summary: dict[str, Any],
    upstream: dict[str, Any],
) -> tuple[bool, bool]:
    current = reviews.get(case_id)
    default_reviewer = current.get("reviewer") or os.getenv("USER", "")

    st.markdown("### Decision")
    st.caption(
        "The downstream positive is already established by the pipeline. Your task is to judge how the issue relates to that change and whether intentional harm is supported."
    )

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Issue -> change overlap**  \n{_text(upstream.get('issue_change_alignment')) or 'None'}")
        c2.markdown(f"**Downstream attribution**  \n{_text(summary.get('strongest_attribution')).title()}")
        c3.markdown(f"**Evidence family**  \n{_text(summary.get('archetype'))}")
        st.caption(_text(upstream.get("upstream_summary")))

    with st.form(f"manual_assessment_{case_id}"):
        st.markdown("#### Guided judgement")
        g1, g2, g3 = st.columns(3)
        with g1:
            issue_change_connection = st.selectbox(
                "Does the issue request connect to the security-relevant change?",
                ISSUE_CONNECTION_LABELS,
                index=_select_index(
                    ISSUE_CONNECTION_LABELS,
                    _text(current.get("issue_change_connection")),
                ),
            )
        with g2:
            goal_effect_relationship = st.selectbox(
                "How does the security effect relate to the stated goal?",
                GOAL_EFFECT_LABELS,
                index=_select_index(
                    GOAL_EFFECT_LABELS,
                    _text(current.get("goal_effect_relationship")),
                ),
            )
        with g3:
            benign_explanation = st.selectbox(
                "How plausible is a benign explanation?",
                BENIGN_EXPLANATION_LABELS,
                index=_select_index(
                    BENIGN_EXPLANATION_LABELS,
                    _text(current.get("benign_explanation")),
                ),
            )

        st.markdown("#### Study taxonomy")
        a1, a2 = st.columns(2)
        with a1:
            maliciousness = st.selectbox(
                "Maliciousness level",
                MALICIOUSNESS_LABELS,
                index=_select_index(MALICIOUSNESS_LABELS, _text(current.get("maliciousness"))),
            )
            intent = st.selectbox(
                "Likely intent",
                INTENT_LABELS,
                index=_select_index(INTENT_LABELS, _text(current.get("intent"))),
            )
            confidence = st.selectbox(
                "Assessment confidence",
                CONFIDENCE_LABELS,
                index=_select_index(CONFIDENCE_LABELS, _text(current.get("confidence"))),
            )
        with a2:
            disguise = st.selectbox(
                "Issue disguise / framing",
                DISGUISE_LABELS,
                index=_select_index(DISGUISE_LABELS, _text(current.get("disguise"))),
            )
            review_status = st.selectbox(
                "Review status",
                REVIEW_STATUSES,
                index=_select_index(REVIEW_STATUSES, _text(current.get("review_status"))),
            )
            reviewer = st.text_input("Reviewer", value=default_reviewer)

        rationale = st.text_area(
            "Rationale",
            value=_text(current.get("rationale")),
            height=130,
            placeholder=(
                "Summarise the issue request, the downstream security effect, the connection between them, "
                "and why the case is malicious/suspicious/benign/unclear."
            ),
        )
        technical_notes = st.text_area(
            "Technical / attribution notes",
            value=_text(current.get("technical_notes")),
            height=90,
            placeholder="Record scanner duplication, lockfile regeneration, test/mock context, CodeQL flow details, or other caveats.",
        )

        save_col, next_col = st.columns(2)
        saved = save_col.form_submit_button("Save assessment", width="stretch", type="primary")
        saved_next = next_col.form_submit_button("Save + next case ->", width="stretch")

    if saved or saved_next:
        reviews.save(
            case_id=case_id,
            review_status=review_status,
            maliciousness=maliciousness,
            intent=intent,
            disguise=disguise,
            confidence=confidence,
            issue_change_connection=issue_change_connection,
            goal_effect_relationship=goal_effect_relationship,
            benign_explanation=benign_explanation,
            rationale=rationale,
            technical_notes=technical_notes,
            reviewer=reviewer,
        )
    return saved, saved_next


def _detail_screen(
    layer: ResearchLayer,
    store: ParquetStore,
    reviews: ReviewStore,
    case_id: int,
) -> None:
    summary_rows = layer.case_summary[layer.case_summary["case_id"] == int(case_id)]
    case = layer.case(case_id)
    if case is None or summary_rows.empty:
        st.error("This case is not part of the introduced-finding review cohort.")
        if st.button("<- Back to review queue"):
            st.session_state.pop("rq_selected_case", None)
            st.rerun()
        return

    summary = summary_rows.iloc[0].to_dict()
    upstream = layer.case_upstream(case_id)
    events = layer.case_events(case_id)
    attribution = layer.case_attribution(case_id)

    nav_left, nav_mid, nav_right = st.columns([1.2, 4, 1.4])
    if nav_left.button("<- Back to queue", width="stretch"):
        st.session_state.pop("rq_selected_case", None)
        st.rerun()
    nav_mid.caption("Queue filters and page are preserved.")
    next_id = _next_case_id(case_id)
    if nav_right.button("Next case ->", disabled=next_id is None, width="stretch") and next_id is not None:
        st.session_state["rq_selected_case"] = next_id
        st.session_state[f"rq_workspace_{next_id}"] = "Upstream"
        st.rerun()

    st.title(f"Case #{case_id}")
    st.markdown(
        f"### {_text(case.get('repo_full_name'))} · Issue #{_text(case.get('issue_number'))} -> PR #{_text(case.get('pr_number'))}"
    )
    st.markdown(f"**{_text(case.get('issue_title'))}**")

    link1, link2, link3 = st.columns([1, 1, 2])
    if case.get("issue_url"):
        link1.link_button("Open GitHub issue", str(case["issue_url"]), width="stretch")
    if case.get("pr_url"):
        link2.link_button("Open pull request", str(case["pr_url"]), width="stretch")
    link3.caption(
        f"Upstream overlap: {_text(summary.get('issue_change_alignment'))} · "
        f"Downstream: {_text(summary.get('archetype'))} · "
        f"Review priority: {_text(summary.get('review_priority'))}"
    )

    workspace = st.radio(
        "Case workspace",
        ["Upstream", "Downstream", "Decision"],
        horizontal=True,
        key=f"rq_workspace_{case_id}",
        label_visibility="collapsed",
    )
    st.markdown("---")

    if workspace == "Upstream":
        _render_upstream_tab(layer, store, case, case_id)
    elif workspace == "Downstream":
        _render_downstream_tab(layer, store, case, summary, events, attribution, case_id)
    else:
        saved, saved_next = _manual_assessment_form(case_id, reviews, summary, upstream)
        if saved_next:
            target = _next_case_id(case_id)
            if target is not None:
                st.session_state["rq_selected_case"] = target
                st.session_state[f"rq_workspace_{target}"] = "Upstream"
            else:
                st.session_state.pop("rq_selected_case", None)
            st.rerun()
        if saved:
            st.success("Manual assessment saved locally.")
            st.rerun()


def render_manual_review(
    layer: ResearchLayer,
    store: ParquetStore,
    reviews: ReviewStore,
) -> None:
    selected = st.session_state.get("rq_selected_case")
    if selected is None:
        _queue_screen(layer, reviews)
    else:
        _detail_screen(layer, store, reviews, int(selected))


def render_evidence_insights(
    layer: ResearchLayer,
    reviews: ReviewStore,
) -> None:
    st.title("Evidence insights")
    st.caption(
        "Descriptive EDA for the static-analysis-positive cohort. This page summarises what you can already show without further GitHub enrichment."
    )

    events = layer.events.copy()
    cases = layer.case_summary.copy()
    attribution = layer.attribution.copy()

    st.markdown("### Upstream: issue -> downstream overlap")
    left, right = st.columns(2)
    with left:
        alignment = (
            cases.groupby("issue_change_alignment", as_index=False)
            .agg(cases=("case_id", "count"))
        )
        alignment["order"] = alignment["issue_change_alignment"].map(_ALIGNMENT_ORDER).fillna(9)
        st.dataframe(alignment.sort_values("order").drop(columns=["order"]), hide_index=True, width="stretch")
    with right:
        same_author = pd.DataFrame(
            {
                "author_relationship": ["Issue author = PR author", "Different issue/PR authors"],
                "cases": [
                    int(cases["same_issue_pr_author"].fillna(False).sum()),
                    int((~cases["same_issue_pr_author"].fillna(False).astype(bool)).sum()),
                ],
            }
        )
        st.dataframe(same_author, hide_index=True, width="stretch")

    overlap_metrics = st.columns(4)
    overlap_metrics[0].metric("Issue names affected package", _fmt((cases["matched_packages"].fillna("") != "").sum()))
    overlap_metrics[1].metric("Issue names affected version", _fmt((cases["matched_versions"].fillna("") != "").sum()))
    overlap_metrics[2].metric("Issue names relevant file", _fmt((cases["matched_files"].fillna("") != "").sum()))
    overlap_metrics[3].metric("Issue names vulnerability ID", _fmt((cases["matched_vulnerability_ids"].fillna("") != "").sum()))

    cue_counter: Counter[str] = Counter()
    for value in cases["review_cues"].fillna("").astype(str):
        for cue in [item.strip() for item in value.split(",") if item.strip()]:
            cue_counter[cue] += 1
    if cue_counter:
        st.markdown("#### Review-cue wording in issue descriptions")
        cue_frame = pd.DataFrame(
            [{"cue": cue, "cases": count} for cue, count in cue_counter.most_common()]
        )
        st.dataframe(cue_frame, hide_index=True, width="stretch")
        st.caption("These are search/reading cues only. They do not establish maliciousness.")

    st.markdown("### PR size for the positive cohort")
    size_cols = st.columns(4)
    size_cols[0].metric("Median additions", _fmt(cases["pr_additions"].median()))
    size_cols[1].metric("Median deletions", _fmt(cases["pr_deletions"].median()))
    size_cols[2].metric("Median changed files", _fmt(cases["changed_files_count"].median()))
    size_cols[3].metric("Median commits", _fmt(cases["commits_count"].median()))

    st.markdown("### Downstream: scanner redundancy and canonicalisation")
    c1, c2, c3 = st.columns(3)
    c1.metric("Raw introduced findings", _fmt(len(attribution)))
    c2.metric("Canonical security events", _fmt(len(events)))
    c3.metric("Collapsed records", _fmt(max(0, len(attribution) - len(events))))

    scanner = (
        attribution.groupby("scanner", as_index=False)
        .agg(findings=("finding_id", "count"), cases=("case_id", "nunique"))
        .sort_values("findings", ascending=False)
    )
    st.dataframe(scanner, hide_index=True, width="stretch")

    st.markdown("### Evidence family")
    family = (
        events.groupby("event_family", as_index=False)
        .agg(events=("event_id", "count"), cases=("case_id", "nunique"), raw_findings=("raw_finding_count", "sum"))
        .sort_values("cases", ascending=False)
    )
    st.dataframe(family, hide_index=True, width="stretch")

    left, right = st.columns(2)
    with left:
        st.markdown("### Attribution strength")
        attr = events.groupby("attribution_strength", as_index=False).agg(
            events=("event_id", "count"), cases=("case_id", "nunique")
        )
        attr["order"] = attr["attribution_strength"].map({"strong": 0, "moderate": 1, "weak": 2, "none": 3})
        st.dataframe(attr.sort_values("order").drop(columns=["order"]), hide_index=True, width="stretch")
    with right:
        st.markdown("### Evidence context")
        context = (
            events.groupby("primary_context", as_index=False)
            .agg(events=("event_id", "count"), cases=("case_id", "nunique"))
            .sort_values("events", ascending=False)
        )
        st.dataframe(context, hide_index=True, width="stretch")

    st.markdown("### Code-analysis rules")
    code = attribution[attribution["event_family"] == "Code vulnerability"].copy()
    if not code.empty:
        rules = (
            code.groupby(["scanner", "rule_id"], as_index=False)
            .agg(findings=("finding_id", "count"), cases=("case_id", "nunique"))
            .sort_values("findings", ascending=False)
            .head(30)
        )
        st.dataframe(rules, hide_index=True, width="stretch")

    st.markdown("### What is not required for tomorrow")
    st.info(
        "The current snapshot already contains the basics needed to present all positive cases: issue text/author, PR author/state/size/timing, "
        "changed files and patches, scanner findings, canonical events, and PR attribution. Account age, prior repo activity, author-association, "
        "maintainer review text, and historical merge/close rates would require GitHub enrichment and can be added later."
    )

    d1, d2 = st.columns(2)
    d1.download_button(
        "Download upstream findings CSV",
        _upstream_csv(layer),
        file_name="upstream_findings_static_analysis_positive_cases.csv",
        mime="text/csv",
        width="stretch",
    )
    d2.download_button(
        "Download manual labels CSV",
        reviews.export_csv_bytes(),
        file_name="manual_issue_review_labels.csv",
        mime="text/csv",
        width="stretch",
    )
