#Group members:
#Tazeem Tayob - 2659956
#Arno Strauss - 2613224
#Zeeshaan Ebrahim - 2543004.

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import streamlit as st

from ui.parquet_store import ParquetBackendError, ParquetStore
from ui.research_layer import ResearchLayer
from ui.review_store import (
    CONFIDENCE_LABELS,
    DISGUISE_LABELS,
    INTENT_LABELS,
    MALICIOUSNESS_LABELS,
    REVIEW_STATUSES,
    ReviewStore,
)

_PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}
_SEVERITY_ORDER = {
    "critical": 7,
    "high": 6,
    "error": 5,
    "medium": 4,
    "warning": 3,
    "low": 2,
    "unknown": 0,
    "": 0,
}


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


def _review_frame(layer: ResearchLayer, reviews: ReviewStore) -> pd.DataFrame:
    queue = layer.case_summary.copy()
    labels = reviews.frame()
    if labels.empty:
        for column, default in (
            ("review_status", "Unreviewed"),
            ("maliciousness", "Unreviewed"),
            ("intent", "Unassigned"),
            ("disguise", "Unassigned"),
            ("confidence", "Unassigned"),
            ("rationale", ""),
            ("technical_notes", ""),
            ("reviewer", ""),
        ):
            queue[column] = default
        return queue

    labels = labels[
        [
            "case_id",
            "review_status",
            "maliciousness",
            "intent",
            "disguise",
            "confidence",
            "rationale",
            "technical_notes",
            "reviewer",
            "updated_at",
        ]
    ]
    queue = queue.merge(labels, how="left", on="case_id")
    defaults = {
        "review_status": "Unreviewed",
        "maliciousness": "Unreviewed",
        "intent": "Unassigned",
        "disguise": "Unassigned",
        "confidence": "Unassigned",
        "rationale": "",
        "technical_notes": "",
        "reviewer": "",
        "updated_at": "",
    }
    for column, default in defaults.items():
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
    reviewed_pct = progress["reviewed"] / total
    st.progress(reviewed_pct, text=f"Manual validation progress: {progress['reviewed']}/{progress['total']} cases")


def render_study_overview(
    layer: ResearchLayer,
    reviews: ReviewStore,
) -> None:
    st.title("Finding and Studying Potentially Malicious GitHub Issues")
    st.caption(
        "Current study stage: deterministic candidate mining → issue/PR linking → static-analysis delta → "
        "PR-attribution analysis → manual validation. No LLM classifier is required for this review workflow."
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
        f"Static analysis narrows {stats.total_cases:,} included candidates to {stats.positive_cases:,} "
        f"cases with introduced findings ({positive_pct:.1f}%). These are candidates for manual assessment, "
        "not automatically malicious issues."
    )

    _progress_metrics(layer, reviews)

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Positive-case archetypes")
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

    with right:
        st.markdown("### Review priority")
        priority = (
            layer.case_summary.groupby("review_priority", as_index=False)
            .agg(cases=("case_id", "count"))
        )
        priority["order"] = priority["review_priority"].map(_PRIORITY_ORDER)
        priority = priority.sort_values("order").drop(columns=["order"])
        st.dataframe(priority, hide_index=True, width="stretch")
        st.caption(
            "Review priority is an evidence-quality/workload heuristic only. It is deliberately not a maliciousness score."
        )

    st.markdown("### What the manual review is deciding")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Maliciousness level**")
        st.write("Clearly malicious → probably malicious → potentially suspicious → benign/artifact/insufficient evidence.")
    with c2:
        st.markdown("**Intent**")
        st.write("Code vulnerability, vulnerable dependency, downgrade, secret exposure, CI/CD manipulation, or another intent.")
    with c3:
        st.markdown("**Disguise**")
        st.write("Bug fix, security improvement, feature request, maintenance, testing, refactor, or no apparent disguise.")

    st.markdown("### Why the interface canonicalises scanner output")
    duplicate_count = int(layer.case_summary["duplicate_report_count"].sum())
    st.write(
        f"The snapshot contains {stats.introduced_findings:,} raw introduced findings. The review layer collapses "
        f"scanner overlap/repeated reports into {stats.unique_events:,} canonical events, removing approximately "
        f"{duplicate_count:,} duplicate/redundant records from the primary review surface. Raw scanner evidence remains available on demand."
    )

    st.download_button(
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

    token = search.strip().lower()
    if token:
        mask = (
            filtered["repo_full_name"].fillna("").str.lower().str.contains(token, regex=False)
            | filtered["issue_title"].fillna("").str.lower().str.contains(token, regex=False)
            | filtered["case_id"].astype(str).eq(token)
            | filtered["issue_number"].astype(str).eq(token)
        )
        filtered = filtered[mask]

    filtered["_priority"] = filtered["review_priority"].map(_PRIORITY_ORDER).fillna(3)
    filtered = filtered.sort_values(
        ["_priority", "review_status", "unique_event_count", "repo_stars", "case_id"],
        ascending=[True, True, True, False, True],
    ).drop(columns=["_priority"])
    return filtered.reset_index(drop=True)


def _queue_screen(
    layer: ResearchLayer,
    reviews: ReviewStore,
) -> None:
    st.title("Manual review queue")
    st.caption(
        "138 cases have at least one introduced static-analysis finding. Review the causal evidence, then assign the study taxonomy manually."
    )
    _progress_metrics(layer, reviews)

    queue = _review_frame(layer, reviews)
    archetypes = ["All"] + sorted(queue["archetype"].dropna().unique().tolist())

    f1, f2, f3, f4, f5 = st.columns([1, 1.25, 1, 1.35, 1.6])
    with f1:
        status = st.selectbox("Review status", ["All"] + REVIEW_STATUSES, key="rq_status")
    with f2:
        maliciousness = st.selectbox("Manual label", ["All"] + MALICIOUSNESS_LABELS, key="rq_maliciousness")
    with f3:
        priority = st.selectbox("Review priority", ["All", "High", "Medium", "Low"], key="rq_priority")
    with f4:
        archetype = st.selectbox("Evidence family", archetypes, key="rq_archetype")
    with f5:
        search = st.text_input("Search repo / issue / case", key="rq_search")

    filtered = _filter_queue(queue, status, maliciousness, priority, archetype, search)
    st.session_state["rq_case_ids"] = [int(value) for value in filtered["case_id"].tolist()]

    page_size = 20
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size)
    page = int(st.session_state.get("rq_page", 1))
    page = min(max(page, 1), total_pages)
    st.session_state["rq_page"] = page

    top_left, top_mid, top_right = st.columns([1, 2, 1])
    if top_left.button("← Previous page", disabled=page <= 1, width="stretch"):
        st.session_state["rq_page"] = page - 1
        st.rerun()
    top_mid.caption(f"{len(filtered):,} matching cases · page {page}/{total_pages}")
    if top_right.button("Next page →", disabled=page >= total_pages, width="stretch"):
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
            main, evidence, action = st.columns([3.4, 2.1, 1.1])
            with main:
                st.markdown(
                    f"**#{case_id} · {_text(row.get('repo_full_name'))}**  \n"
                    f"Issue #{_text(row.get('issue_number'))}: {_text(row.get('issue_title'))}"
                )
                st.caption(_text(row.get("why_flagged")))
                st.caption(
                    f"PR #{_text(row.get('pr_number'))} · +{_fmt(row.get('pr_additions'))} / "
                    f"-{_fmt(row.get('pr_deletions'))} · {_fmt(row.get('changed_files_count'))} changed files"
                )

            with evidence:
                st.markdown(f"**{_text(row.get('archetype'))}**")
                st.write(
                    f"{_fmt(row.get('unique_event_count'))} unique events · "
                    f"{_fmt(row.get('raw_finding_count'))} raw findings"
                )
                st.caption(
                    f"Attribution: {_text(row.get('strongest_attribution')).title()} · "
                    f"Priority: {_text(row.get('review_priority'))}"
                )
                if int(row.get("duplicate_report_count") or 0) > 0:
                    st.caption(f"{_fmt(row.get('duplicate_report_count'))} redundant scanner records collapsed")

            with action:
                label = _text(row.get("maliciousness")) or "Unreviewed"
                st.caption(f"Label: {label}")
                if st.button("Inspect →", key=f"rq_open_{case_id}", width="stretch", type="primary"):
                    st.session_state["rq_selected_case"] = case_id
                    st.rerun()


def _select_index(options: list[str], value: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


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


def _render_event(event: dict[str, Any], attribution: pd.DataFrame) -> None:
    with st.expander(_event_heading(event), expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Attribution", _text(event.get("attribution_strength")).title())
        c2.metric("Raw scanner records", _fmt(event.get("raw_finding_count")))
        c3.metric("Scanners", _fmt(event.get("scanner_count")))
        c4.metric("Context", _text(event.get("primary_context")) or "unknown")

        family = _text(event.get("event_family"))
        if family.startswith("Dependency"):
            package = _text(event.get("package")) or "(package unavailable)"
            version = _text(event.get("version"))
            old_version = _text(event.get("old_version"))
            new_version = _text(event.get("new_version"))
            st.markdown(f"**Package:** `{package}`")
            if old_version or new_version:
                st.markdown(f"**Version change:** `{old_version or '?'} → {new_version or '?'}`")
            elif version:
                st.markdown(f"**Affected version:** `{version}`")
            if event.get("canonical_vuln_id"):
                st.markdown(f"**Canonical vulnerability:** `{_text(event.get('canonical_vuln_id'))}`")
            if event.get("fixed_version"):
                st.markdown(f"**Known fixed version:** `{_text(event.get('fixed_version'))}`")

        st.markdown("**Why this is attributable to the PR**")
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
                    "attribution_strength",
                    "description_preview",
                ]
            ]
            st.markdown("**Underlying scanner records**")
            st.dataframe(display, hide_index=True, width="stretch")


def _manual_assessment_form(
    case_id: int,
    reviews: ReviewStore,
) -> tuple[bool, bool]:
    current = reviews.get(case_id)
    default_reviewer = current.get("reviewer") or os.getenv("USER", "")

    st.markdown("### Manual research assessment")
    st.caption(
        "The static-analysis evidence selects the case for review. This manual assessment is the study's ground-truth judgement."
    )

    with st.form(f"manual_assessment_{case_id}"):
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
            "Rationale for the maliciousness judgement",
            value=_text(current.get("rationale")),
            height=120,
            placeholder=(
                "Explain whether the issue/PR appears intentionally harmful, benign, or ambiguous. "
                "Base this on the issue request, PR change, introduced security event, and context."
            ),
        )
        technical_notes = st.text_area(
            "Technical / attribution notes",
            value=_text(current.get("technical_notes")),
            height=90,
            placeholder="Record scanner noise, baseline concerns, lockfile regeneration, test/mock context, or other caveats.",
        )

        save_col, next_col = st.columns(2)
        saved = save_col.form_submit_button("Save assessment", width="stretch", type="primary")
        saved_next = next_col.form_submit_button("Save + next case →", width="stretch")

    if saved or saved_next:
        reviews.save(
            case_id=case_id,
            review_status=review_status,
            maliciousness=maliciousness,
            intent=intent,
            disguise=disguise,
            confidence=confidence,
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
        if st.button("← Back to review queue"):
            st.session_state.pop("rq_selected_case", None)
            st.rerun()
        return

    summary = summary_rows.iloc[0].to_dict()
    events = layer.case_events(case_id)
    attribution = layer.case_attribution(case_id)
    detail = store.one("SELECT * FROM pq_case_detail WHERE case_id = ? LIMIT 1", [case_id]) or {}

    nav_left, nav_mid, nav_right = st.columns([1.2, 4, 1.4])
    if nav_left.button("← Back to queue", width="stretch"):
        st.session_state.pop("rq_selected_case", None)
        st.rerun()
    nav_mid.caption(
        "Your queue filters and page are preserved when you return."
    )
    next_id = _next_case_id(case_id)
    if nav_right.button("Next case →", disabled=next_id is None, width="stretch") and next_id is not None:
        st.session_state["rq_selected_case"] = next_id
        st.rerun()

    st.title(f"Case #{case_id}")
    st.markdown(
        f"### {_text(case.get('repo_full_name'))} · Issue #{_text(case.get('issue_number'))} → PR #{_text(case.get('pr_number'))}"
    )
    st.markdown(f"**{_text(case.get('issue_title'))}**")

    link1, link2, link3 = st.columns([1, 1, 2])
    if case.get("issue_url"):
        link1.link_button("Open GitHub issue", str(case["issue_url"]), width="stretch")
    if case.get("pr_url"):
        link2.link_button("Open pull request", str(case["pr_url"]), width="stretch")
    link3.caption(
        f"Review priority: {_text(summary.get('review_priority'))} · {_text(summary.get('review_priority_reason'))}"
    )

    st.markdown("## Why static analysis flagged this case")
    st.info(_text(summary.get("why_flagged")))

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Unique security events", _fmt(summary.get("unique_event_count")))
    c2.metric("Raw scanner findings", _fmt(summary.get("raw_finding_count")))
    c3.metric("Redundant records collapsed", _fmt(summary.get("duplicate_report_count")))
    c4.metric("Strongly attributed events", _fmt(summary.get("strong_attribution_events")))
    c5.metric("Evidence family", _text(summary.get("archetype")))

    if int(summary.get("test_context_events") or 0) > 0:
        st.warning(
            f"{_fmt(summary.get('test_context_events'))} canonical event(s) occur in tests, fixtures, or mocks. "
            "Treat these as lower-context security evidence unless the test material itself creates real exposure."
        )
    if int(summary.get("lockfile_events") or 0) >= 20:
        st.warning(
            "This is a bulk lockfile/dependency case. Raw vulnerability counts may be inflated by scanner overlap or "
            "a dependency graph becoming newly observable; inspect attribution before treating all findings as introduced behaviour."
        )

    st.markdown("### Canonical introduced security events")
    for event in events.to_dict("records"):
        _render_event(event, attribution)

    st.markdown("### PR change surface")
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
    else:
        relevant_paths: set[str] = set()
        for event in events.to_dict("records"):
            for path in _text(event.get("primary_files")).split(","):
                if path.strip():
                    relevant_paths.add(path.strip())
            for path in _text(event.get("codeflow_changed_paths")).split(","):
                if path.strip():
                    relevant_paths.add(path.strip())
        files = files.copy()
        files.insert(0, "relevant_to_static_analysis", files["filename"].isin(relevant_paths))
        files = files.sort_values(["relevant_to_static_analysis", "filename"], ascending=[False, True])
        st.dataframe(files, hide_index=True, width="stretch", height=300)

        patchable = files[files["has_patch"] == True]  # noqa: E712
        if not patchable.empty:
            options = patchable.to_dict("records")
            selected_file = st.selectbox(
                "Inspect a changed-file patch",
                options,
                format_func=lambda item: (
                    ("★ " if item.get("relevant_to_static_analysis") else "")
                    + f"{item.get('filename')} (+{_fmt(item.get('additions'))}/-{_fmt(item.get('deletions'))})"
                ),
                key=f"rq_patch_{case_id}",
            )
            if st.button("Load patch", key=f"rq_patch_load_{case_id}_{int(selected_file['file_id'])}"):
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

    saved, saved_next = _manual_assessment_form(case_id, reviews)
    if saved_next:
        target = _next_case_id(case_id)
        if target is not None:
            st.session_state["rq_selected_case"] = target
        else:
            st.session_state.pop("rq_selected_case", None)
        st.rerun()
    if saved:
        st.success("Manual assessment saved locally.")
        st.rerun()

    st.markdown("### Supporting context")
    with st.expander("Issue request", expanded=False):
        st.markdown(_text(detail.get("issue_body")) or "_No issue body stored._")
    with st.expander("Pull-request description", expanded=False):
        st.markdown(_text(detail.get("pr_body")) or "_No PR body stored._")
    with st.expander("Candidate-selection context (normally hidden)", expanded=False):
        st.caption(
            "These upstream features explain why the issue entered the candidate pipeline. They are not treated as the cause of the static-analysis positive."
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
    with st.expander("Raw scanner evidence / JSON", expanded=False):
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
        "EDA for the static-analysis-positive cohort. These summaries are intended to guide review and explain the methodology, not to predict maliciousness."
    )

    events = layer.events.copy()
    cases = layer.case_summary.copy()
    attribution = layer.attribution.copy()

    st.markdown("### Scanner redundancy and canonicalisation")
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
        attr = (
            events.groupby("attribution_strength", as_index=False)
            .agg(events=("event_id", "count"), cases=("case_id", "nunique"))
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

    st.markdown("### Highest raw-count cases versus canonical events")
    comparison = cases[
        [
            "case_id",
            "repo_full_name",
            "archetype",
            "raw_finding_count",
            "unique_event_count",
            "duplicate_report_count",
            "strong_attribution_events",
            "review_priority",
        ]
    ].sort_values("raw_finding_count", ascending=False).head(30)
    st.dataframe(comparison, hide_index=True, width="stretch")
    st.caption(
        "Large raw finding counts are often dominated by dependency lockfiles and scanner overlap. The manual queue therefore does not rank cases by raw finding count alone."
    )

    review_frame = reviews.frame()
    if not review_frame.empty:
        reviewed = review_frame[review_frame["review_status"] == "Reviewed"]
        if not reviewed.empty:
            st.markdown("### Manual labels so far")
            labels = (
                reviewed.groupby("maliciousness", as_index=False)
                .agg(cases=("case_id", "count"))
                .sort_values("cases", ascending=False)
            )
            st.dataframe(labels, hide_index=True, width="stretch")

    st.download_button(
        "Download manual labels CSV",
        reviews.export_csv_bytes(),
        file_name="manual_issue_review_labels.csv",
        mime="text/csv",
        width="stretch",
    )
