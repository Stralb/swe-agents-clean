from __future__ import annotations

from ui.views.distributed_runtime import render_distributed_runtime

import json
import html
import math
from pathlib import Path
from urllib.parse import quote, unquote

import pandas as pd
import streamlit as st

from src.db.database import Database
from src.pipeline.case_exporter import selected_evidence_zip
from ui.retrieval import (
    BASE_QUERY,
    STREAMS,
    ai_marker_label,
    derive_query_terms,
    derive_stage,
    display_label,
    filter_by_terms,
    generated_query,
    priority_score,
    render_query_html,
    render_term_chip,
    signal_label,
    row_signal_label,
)

OVERVIEW_QUERY = """
SELECT
    c.id AS case_id,
    r.full_name AS repo,
    r.html_url AS repo_url,
    i.title AS issue_title,
    i.body AS issue_body,
    i.url AS issue_url,
    p.title AS pr_title,
    p.body AS pr_body,
    p.url AS pr_url,
    c.downstream_signal,
    c.ai_cohort,
    c.auto_tags,
    c.status,
    c.final_label,
    COALESCE(i.word_count, 0) AS issue_words,
    COALESCE((SELECT COUNT(*) FROM scanner_findings sf WHERE sf.case_id=c.id), 0) AS finding_count,
    COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM case_tags ct JOIN tags t ON ct.tag_id=t.id WHERE ct.case_id=c.id), '') AS manual_tags,
    COALESCE((SELECT GROUP_CONCAT(pf.filename, ',') FROM pr_files pf WHERE pf.pr_id=c.pr_id), '') AS file_names,
    COALESCE((SELECT GROUP_CONCAT(am.matched_tool, ',') FROM ai_markers am WHERE am.case_id=c.id OR am.issue_id=c.issue_id OR am.pr_id=c.pr_id), '') AS ai_marker_terms,
    COALESCE((SELECT GROUP_CONCAT(ipl.method, ',') FROM issue_pr_links ipl WHERE ipl.issue_id=c.issue_id AND ipl.pr_id=c.pr_id), '') AS link_methods,
    COALESCE((SELECT GROUP_CONCAT(cr.term, ',') FROM case_retrievals cr WHERE cr.case_id=c.id), '') AS retrieval_terms,
    COALESCE((SELECT GROUP_CONCAT(sr.scanner || ':' || sr.status, ',') FROM scanner_runs sr WHERE sr.pr_id=c.pr_id), '') AS scanner_statuses,
    COALESCE((SELECT GROUP_CONCAT(sj.job_type || ':' || sj.status, ',') FROM scanner_jobs sj WHERE sj.case_id=c.id), '') AS scanner_job_statuses
FROM cases c
JOIN repos r ON c.repo_id = r.id
JOIN issues i ON c.issue_id = i.id
JOIN pull_requests p ON c.pr_id = p.id
ORDER BY
  CASE c.status WHEN 'needs_review' THEN 0 WHEN 'scanner_running' THEN 1 WHEN 'metadata_collected' THEN 2 WHEN 'scan_blocked' THEN 3 WHEN 'scanner_blocked' THEN 3 WHEN 'scanned_clean' THEN 4 WHEN 'reviewed' THEN 5 ELSE 6 END,
  c.updated_at DESC, c.id DESC
"""

EXCLUSION_MAP = {
    "no_same_repo_linked_issue": ("Not eligible as study cases", "No same-repo linked issue", "GraphQL/metadata did not show an issue in the same repository as the PR."),
    "not_tool_applicable": ("Not relevant code changes", "No applicable downstream worker", "Changed artifacts were not applicable to CodeQL, OSV, downgrade detection, or secret scanning."),
    "repo_filter:archived": ("Repo universe filter", "Archived repo", "Repository is archived and outside the active repo universe."),
    "repo_filter:fork": ("Repo universe filter", "Fork", "Repository is a fork and outside the canonical repo universe."),
    "outside_lookback": ("Not eligible as study cases", "Too old", "PR or issue was outside the configured lookback window."),
    "unmerged_pr": ("Not eligible as study cases", "Not merged", "PR was not merged, so it did not produce a downstream code change."),
    "no_linked_issue": ("Not eligible as study cases", "No linked issue", "No same-repo issue could be linked to the PR."),
    "linked_item_is_pr": ("Not eligible as study cases", "Linked item was a PR", "The reference pointed to another PR, not an issue."),
    "non_behaviour_only": ("Not relevant code changes", "Docs/assets only", "PR only changed docs, images, prose, or other non-behavioural files."),
    "docs_only": ("Not relevant code changes", "Docs only", "PR only changed documentation/prose files."),
    "assets_only": ("Not relevant code changes", "Assets only", "PR only changed images or static assets."),
    "format_only": ("Not relevant code changes", "Formatting only", "PR appeared to be formatting-only maintenance."),
    "bot_maintenance": ("Not relevant code changes", "Bot maintenance", "Automated dependency, formatting, or maintenance PR excluded from the study sample."),
    "issue_filter": ("Not relevant code changes", "Issue filtered out", "Linked issue did not pass configured issue-level filters."),
    "inaccessible_issue": ("Could not inspect properly", "Issue unavailable", "Linked issue could not be fetched or accessed."),
    "inaccessible_pr": ("Could not inspect properly", "PR unavailable", "PR data could not be fetched or accessed."),
    "pr_files_unavailable": ("Could not inspect properly", "PR file list unavailable", "GitHub could not provide the changed-file list for the PR."),
    "repo_pr_list_unavailable": ("Could not inspect properly", "Repo PR list unavailable", "GitHub could not provide the repository PR list."),
    "processing_error": ("Could not inspect properly", "Processing error", "The miner hit an unexpected error while processing this item."),
    "duplicate": ("Sampling limits / duplicates", "Duplicate", "Same issue-PR pair was already collected."),
    "over_repo_cap": ("Sampling limits / duplicates", "Repo cap reached", "Repository reached the configured per-repo case limit."),
}


def _open_case(case_id: int, queue_ids: list[int] | None = None) -> None:
    st.session_state["selected_case_id"] = int(case_id)
    if queue_ids:
        st.session_state["review_queue_ids"] = [int(x) for x in queue_ids]
    st.session_state["nav"] = "Case Review"
    st.rerun()


def _render_metric(label: str, value: str | int, help_text: str) -> str:
    return (
        "<div class='metric-mini' title='" + html.escape(help_text) + "'>"
        "<div class='label'>" + html.escape(label) + " <span class='hint'>?</span></div>"
        "<div class='value'>" + html.escape(str(value)) + "</div>"
        "</div>"
    )


def _row_terms(rows: list[dict]) -> dict[int, list[str]]:
    return {int(r["case_id"]): derive_query_terms(r) for r in rows}


def _consume_query_term_toggle() -> None:
    """Toggle stream terms from lightweight HTML chip links.

    Streamlit buttons inside custom coloured cards render poorly. Indicator-param
    links keep the stream cards fully custom, compact, and coloured while still
    letting the user click terms to filter the case list.
    """
    try:
        raw = st.query_params.get("toggle_term")
    except Exception:
        raw = None
    if not raw:
        return
    term = unquote(raw[0] if isinstance(raw, list) else raw)
    selected = set(st.session_state.get("query_terms_selected", []))
    if term in selected:
        selected.remove(term)
    else:
        selected.add(term)
    st.session_state["query_terms_selected"] = sorted(selected)
    try:
        del st.query_params["toggle_term"]
    except Exception:
        try:
            st.query_params.clear()
        except Exception:
            pass
    st.rerun()


def _stream_chip_html(term: str, count: int, selected: bool, color: str) -> str:
    encoded = quote(term, safe="")
    cls = "query-chip-link query-chip-selected" if selected else "query-chip-link"
    style = f"--stream-color:{color}; color:{color}; border-color:{color}; background:{color}12;"
    return (
        f'<a class="{cls}" style="{style}" href="?toggle_term={encoded}" title="Click to filter by this post-inclusion indicator">'
        f'{html.escape(term)} <span class="term-count">{int(count)}</span></a>'
    )


def _render_query_builder(rows: list[dict]) -> list[str]:
    if "query_terms_selected" not in st.session_state:
        st.session_state["query_terms_selected"] = []
    if "query_match_mode" not in st.session_state:
        st.session_state["query_match_mode"] = "any"
    _consume_query_term_toggle()

    counts: dict[str, int] = {}
    for r in rows:
        for term in derive_query_terms(r):
            counts[term] = counts.get(term, 0) + 1

    selected_now: set[str] = set(st.session_state.get("query_terms_selected", []))
    with st.expander("Indicator filter", expanded=True):
        cards: list[str] = []
        for stream in STREAMS:
            chips = "".join(
                _stream_chip_html(term, counts.get(term, 0), term in selected_now, stream.color)
                for term in stream.terms
            )
            cards.append(
                f'<div class="stream-card" style="--stream-color:{stream.color}">'
                f'<div class="stream-title">{html.escape(stream.name)}</div>'
                f'<div>{chips}</div>'
                f'</div>'
            )
        st.markdown(
            "<div class='query-panel'>"
            "<div class='query-panel-title'>Indicator filter</div>"
            "<div class='query-base-card'><div class='small-muted'>Structural base frame</div>" + render_query_html() + "</div>"
            "<div class='stream-grid'>" + "".join(cards) + "</div>"
            "</div>",
            unsafe_allow_html=True,
        )

        m1, m2 = st.columns([1.25, 4.75])
        with m1:
            mode = st.segmented_control(
                "Match selected terms",
                options=["Any selected", "All selected"],
                default="Any selected" if st.session_state.get("query_match_mode", "any") == "any" else "All selected",
                help="Any = OR. All = AND overlap across selected query terms.",
            )
            st.session_state["query_match_mode"] = "all" if mode == "All selected" else "any"
        with m2:
            if selected_now:
                active = "".join(f"<div>{render_query_html(term)}</div>" for term in sorted(selected_now))
                st.markdown(f"<div class='active-query-box'><b>Active indicators</b>{active}</div>", unsafe_allow_html=True)
                if st.button("Clear selected query terms"):
                    st.session_state["query_terms_selected"] = []
                    st.rerun()
            else:
                st.caption("Click one or more coloured indicators above to filter visible cases. These indicators were not used for primary retrieval.")
    return list(st.session_state.get("query_terms_selected", []))


def _apply_filters(rows: list[dict], selected_terms: list[str]) -> list[dict]:
    all_stage = ["All", "Validated", "Scanning", "Scan blocked", "Clean", "Needs review", "Reviewed"]
    all_signals = ["All", "Pending", "Clean", "Source-code", "CodeQL", "Secret/CI", "Dependency"]
    ai_values = sorted({ai_marker_label(r) for r in rows if ai_marker_label(r) != "No AI"})
    repos = sorted({str(r.get("repo")) for r in rows if r.get("repo")})
    labels = ["All", "Unreviewed", "Auto-clean", "Benign", "Tool false positive", "Benign security fix", "Security regression candidate", "Suspicious issue-linked regression", "High-confidence suspicious", "Unclear"]

    search = st.text_input("Search", placeholder="Search case, repo, stage, signal, AI, query term, label...", label_visibility="collapsed")
    c1, c2, c3, c4, c5 = st.columns(5)
    stage_filter = c1.selectbox("Stage", all_stage, index=0, help="Default is All so freshly scanned clean/scanning cases are visible.")
    signal_filter = c2.selectbox("Signal", all_signals)
    ai_filter = c3.selectbox("AI marker", ["All", "No AI", "Any AI marker"] + ai_values)
    label_filter = c4.selectbox("Label", labels)
    repo_filter = c5.selectbox("Repo", ["All"] + repos)

    filtered: list[dict] = []
    mode = st.session_state.get("query_match_mode", "any")
    for r in rows:
        terms = derive_query_terms(r)
        stage = derive_stage(r)
        sig = row_signal_label(r)
        ai = ai_marker_label(r)
        label = display_label(r)
        if not filter_by_terms(terms, selected_terms, mode):
            continue
        if stage_filter != "All" and stage != stage_filter:
            continue
        if signal_filter != "All" and signal_filter not in sig:
            continue
        if ai_filter == "No AI" and ai != "No AI":
            continue
        if ai_filter == "Any AI marker" and ai == "No AI":
            continue
        if ai_filter not in {"All", "No AI", "Any AI marker"} and ai_filter not in ai:
            continue
        if label_filter != "All" and label != label_filter:
            continue
        if repo_filter != "All" and r.get("repo") != repo_filter:
            continue
        if search:
            hay = " ".join([
                str(r.get("case_id") or ""), str(r.get("repo") or ""), str(r.get("issue_title") or ""), str(r.get("pr_title") or ""),
                stage, sig, ai, label, " ".join(terms), str(r.get("manual_tags") or ""),
            ]).lower()
            if search.lower() not in hay:
                continue
        filtered.append(r)
    return filtered


def _best_case_ids(rows: list[dict]) -> list[int]:
    candidates = [r for r in rows if derive_stage(r) == "Needs review"] or rows
    ranked = sorted(candidates, key=lambda r: (-priority_score(r), str(r.get("case_id") or "")))
    return [int(r["case_id"]) for r in ranked]


def _render_exclusion_audit(db: Database) -> None:
    with st.expander("Excluded items", expanded=False):
        st.caption("Retrieved items that did not become valid cases. These are filtered out before scanner analysis.")
        try:
            reason_rows = db.query("SELECT reason, COUNT(*) AS n FROM excluded_cases GROUP BY reason ORDER BY n DESC, reason")
        except Exception as exc:
            st.caption(f"Exclusion log unavailable: {exc}")
            return
        if not reason_rows:
            st.caption("No logged exclusions yet.")
            return
        groups: dict[str, list[dict]] = {}
        for r in reason_rows:
            group, name, explanation = EXCLUSION_MAP.get(r["reason"], ("Other", str(r["reason"]).replace("_", " ").title(), "Internal exclusion reason."))
            groups.setdefault(group, []).append({"Reason": name, "Count": r["n"], "What it means": explanation, "Raw reason": r["reason"]})
        for group, items in groups.items():
            st.markdown(f"**{group}**")
            st.dataframe(pd.DataFrame(items), hide_index=True, width="stretch")



CHEAP_SCANNERS = (
    "gitleaks",
    "dependency-diff",
    "osv-scanner",
    "semgrep",
)

TRACKED_SCANNERS = CHEAP_SCANNERS + ("codeql",)

TERMINAL_STATUSES = {
    "ok",
    "ok_with_warnings",
    "finding",
    "not_applicable",
    "skipped",
    "complete",
    "completed",
    "error",
    "timeout",
    "tool_missing",
    "parse_failed",
    "partial",
}

ERROR_STATUSES = {
    "error",
    "timeout",
    "tool_missing",
    "parse_failed",
    "partial",
}


def _scan_progress_data(
    db: Database,
) -> tuple[dict, pd.DataFrame]:
    case_ids = [
        int(row["id"])
        for row in db.query(
            "SELECT id FROM cases ORDER BY id"
        )
    ]

    total = len(case_ids)

    latest_runs = db.query(
        """
        SELECT
            sr.case_id,
            sr.scanner,
            sr.status,
            sr.started_at,
            sr.finished_at
        FROM scanner_runs sr
        JOIN (
            SELECT
                case_id,
                scanner,
                MAX(id) AS max_id
            FROM scanner_runs
            WHERE case_id IS NOT NULL
            GROUP BY case_id, scanner
        ) picked
          ON picked.max_id = sr.id
        WHERE sr.scanner IN (
            'gitleaks',
            'dependency-diff',
            'osv-scanner',
            'semgrep',
            'codeql'
        )
        """
    )

    status_by_case: dict[int, dict[str, str]] = {}

    for row in latest_runs:
        case_id = int(row["case_id"])
        scanner = str(row["scanner"])
        status = str(row["status"] or "unknown")

        status_by_case.setdefault(
            case_id,
            {},
        )[scanner] = status

    cheap_finished = 0
    codeql_finished = 0
    problem_cases = 0

    for case_id in case_ids:
        states = status_by_case.get(
            case_id,
            {},
        )

        if all(
            states.get(scanner) in TERMINAL_STATUSES
            for scanner in CHEAP_SCANNERS
        ):
            cheap_finished += 1

        if states.get("codeql") in TERMINAL_STATUSES:
            codeql_finished += 1

        if any(
            status in ERROR_STATUSES
            for status in states.values()
        ):
            problem_cases += 1

    scanner_rows = []

    for scanner in TRACKED_SCANNERS:
        states = [
            case_states.get(scanner)
            for case_states in status_by_case.values()
            if scanner in case_states
        ]

        finished = sum(
            status in TERMINAL_STATUSES
            for status in states
        )

        scanner_rows.append({
            "Scanner": scanner,
            "Finished": "%s/%s" % (
                finished,
                total,
            ),
            "Progress %": (
                round(
                    finished / total * 100,
                    1,
                )
                if total
                else 0.0
            ),
            "OK": sum(
                status in {
                    "ok",
                    "ok_with_warnings",
                    "finding",
                }
                for status in states
            ),
            "Not applicable": states.count(
                "not_applicable"
            ),
            "Running": states.count("running"),
            "Errors": sum(
                status in ERROR_STATUSES
                for status in states
            ),
            "No terminal result": max(
                0,
                total - finished,
            ),
        })

    active_jobs = int(
        (
            db.one(
                """
                SELECT COUNT(*) AS n
                FROM scanner_jobs
                WHERE status IN (
                    'pending',
                    'retry',
                    'running'
                )
                """
            )
            or {}
        ).get("n")
        or 0
    )

    last_activity = (
        db.one(
            """
            SELECT MAX(ts) AS ts
            FROM (
                SELECT MAX(
                    COALESCE(
                        finished_at,
                        started_at
                    )
                ) AS ts
                FROM scanner_runs

                UNION ALL

                SELECT MAX(
                    COALESCE(
                        finished_at,
                        started_at,
                        created_at
                    )
                ) AS ts
                FROM scanner_jobs

                UNION ALL

                SELECT MAX(updated_at) AS ts
                FROM cases

                UNION ALL

                SELECT MAX(updated_at) AS ts
                FROM pr_region_profiles
            )
            """
        )
        or {}
    ).get("ts") or "no recorded activity"

    summary = {
        "total": total,
        "cheap_finished": cheap_finished,
        "codeql_finished": codeql_finished,
        "problem_cases": problem_cases,
        "active_jobs": active_jobs,
        "security_findings": int(
            (
                db.one(
                    """
                    SELECT COUNT(*) AS n
                    FROM scanner_findings
                    WHERE COALESCE(
                        introduced,
                        0
                    ) = 1
                      AND finding_type IN (
                          'vulnerability',
                          'secret',
                          'dependency'
                      )
                    """
                )
                or {}
            ).get("n")
            or 0
        ),
        "quality_findings": int(
            (
                db.one(
                    """
                    SELECT COUNT(*) AS n
                    FROM scanner_findings
                    WHERE COALESCE(
                        introduced,
                        0
                    ) = 1
                      AND finding_type =
                          'code_quality'
                    """
                )
                or {}
            ).get("n")
            or 0
        ),
        "last_activity": last_activity,
    }

    return (
        summary,
        pd.DataFrame(scanner_rows),
    )


def _render_scan_progress(
    db: Database,
) -> None:
    summary, table = _scan_progress_data(db)
    total = summary["total"]

    st.markdown("### Scan progress")

    st.caption(
        "The latest case-level result is used for each "
        "scanner. `not_applicable` counts as finished; "
        "errors are counted separately."
    )

    metrics = [
        (
            "Cheap scans finished",
            "%s/%s" % (
                summary["cheap_finished"],
                total,
            ),
        ),
        (
            "Cheap scans pending",
            max(
                0,
                total - summary["cheap_finished"],
            ),
        ),
        (
            "CodeQL finished",
            "%s/%s" % (
                summary["codeql_finished"],
                total,
            ),
        ),
        (
            "CodeQL pending",
            max(
                0,
                total - summary["codeql_finished"],
            ),
        ),
        (
            "Cases with scan problems",
            summary["problem_cases"],
        ),
        (
            "Active queued jobs",
            summary["active_jobs"],
        ),
        (
            "Security signals",
            summary["security_findings"],
        ),
        (
            "Code-quality notes",
            summary["quality_findings"],
        ),
    ]

    metric_columns = st.columns(4)

    for index, (
        label,
        value,
    ) in enumerate(metrics):
        metric_columns[
            index % 4
        ].metric(
            label,
            value,
        )

    st.progress(
        (
            summary["cheap_finished"] / total
            if total
            else 0.0
        ),
        text=(
            "Cheap scanner coverage: %s/%s"
            % (
                summary["cheap_finished"],
                total,
            )
        ),
    )

    st.progress(
        (
            summary["codeql_finished"] / total
            if total
            else 0.0
        ),
        text=(
            "CodeQL aggregate coverage: %s/%s"
            % (
                summary["codeql_finished"],
                total,
            )
        ),
    )

    st.caption(
        "Last database activity: `%s`"
        % summary["last_activity"]
    )

    with st.expander(
        "Per-scanner status",
        expanded=True,
    ):
        st.dataframe(
            table,
            hide_index=True,
            width="stretch",
        )


if hasattr(st, "fragment"):
    @st.fragment(run_every="10s")
    def _auto_scan_progress(
        db_path: str,
    ) -> None:
        _render_scan_progress(
            Database(
                Path(db_path)
            )
        )
else:
    def _auto_scan_progress(
        db_path: str,
    ) -> None:
        _render_scan_progress(
            Database(
                Path(db_path)
            )
        )


def _region_yield_dataframe(
    db: Database,
) -> pd.DataFrame:
    rows = db.query(
        """
        WITH memberships AS (
            SELECT DISTINCT
                case_id,
                region
            FROM artifact_regions
        ),

        file_counts AS (
            SELECT
                region,
                COUNT(*) AS files
            FROM artifact_regions
            GROUP BY region
        ),

        file_linked_findings AS (
            SELECT DISTINCT
                sf.id AS finding_id,
                sf.case_id,
                ar.region
            FROM scanner_findings sf

            JOIN artifact_regions ar
              ON ar.case_id = sf.case_id
             AND LTRIM(
                    REPLACE(
                        COALESCE(ar.path, ''),
                        '\\',
                        '/'
                    ),
                    './'
                 )
                 =
                 LTRIM(
                    REPLACE(
                        COALESCE(sf.file_path, ''),
                        '\\',
                        '/'
                    ),
                    './'
                 )

            WHERE COALESCE(
                      sf.introduced,
                      0
                  ) = 1
              AND sf.finding_type IN (
                  'vulnerability',
                  'secret',
                  'dependency'
              )
        )

        SELECT
            memberships.region,

            COUNT(
                DISTINCT memberships.case_id
            ) AS pair_count,

            MAX(
                file_counts.files
            ) AS file_count,

            COUNT(
                DISTINCT CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM scanner_runs sr
                        WHERE sr.case_id =
                              memberships.case_id
                    )
                    THEN memberships.case_id
                END
            ) AS scanned_pair_count,

            COUNT(
                DISTINCT file_linked_findings.case_id
            ) AS finding_pair_count,

            COUNT(
                DISTINCT file_linked_findings.case_id
            ) AS introduced_pair_count,

            COUNT(
                DISTINCT CASE
                    WHEN cases.status =
                         'needs_review'
                    THEN memberships.case_id
                END
            ) AS needs_review_count

        FROM memberships

        JOIN cases
          ON cases.id =
             memberships.case_id

        JOIN file_counts
          ON file_counts.region =
             memberships.region

        LEFT JOIN file_linked_findings
          ON file_linked_findings.case_id =
             memberships.case_id
         AND file_linked_findings.region =
             memberships.region

        GROUP BY memberships.region

        ORDER BY
            introduced_pair_count DESC,
            pair_count DESC,
            memberships.region
        """
    )

    if not rows:
        return pd.DataFrame()

    dataframe = pd.DataFrame(rows)

    numeric_columns = (
        "pair_count",
        "file_count",
        "scanned_pair_count",
        "finding_pair_count",
        "introduced_pair_count",
        "needs_review_count",
    )

    for column in numeric_columns:
        dataframe[column] = (
            pd.to_numeric(
                dataframe[column],
                errors="coerce",
            )
            .fillna(0)
            .astype(int)
        )

    dataframe["introduced_yield_pct"] = (
        dataframe.apply(
            lambda row: (
                round(
                    row[
                        "introduced_pair_count"
                    ]
                    / row["pair_count"]
                    * 100,
                    2,
                )
                if row["pair_count"]
                else 0.0
            ),
            axis=1,
        )
    )

    return dataframe


def _render_region_yield_panel(
    db: Database,
) -> None:
    st.markdown("---")

    st.subheader(
        "Artifact-region coverage and yield"
    )

    st.caption(
        "Multi-label view: one issue-PR pair can "
        "appear in several regions. Regions describe "
        "changed artifacts and route analysis; they "
        "do not determine maliciousness."
    )

    dataframe = _region_yield_dataframe(db)

    if dataframe.empty:
        st.info(
            "No persisted artifact-region mappings "
            "are available."
        )
        return

    profiled = int(
        (
            db.one(
                """
                SELECT COUNT(
                    DISTINCT case_id
                ) AS n
                FROM artifact_regions
                """
            )
            or {}
        ).get("n")
        or 0
    )

    mappings = int(
        (
            db.one(
                """
                SELECT COUNT(*) AS n
                FROM artifact_regions
                """
            )
            or {}
        ).get("n")
        or 0
    )

    multi_region = int(
        (
            db.one(
                """
                SELECT COUNT(*) AS n
                FROM (
                    SELECT case_id
                    FROM artifact_regions
                    GROUP BY case_id
                    HAVING COUNT(
                        DISTINCT region
                    ) > 1
                )
                """
            )
            or {}
        ).get("n")
        or 0
    )

    unknown = int(
        (
            db.one(
                """
                SELECT COUNT(
                    DISTINCT case_id
                ) AS n
                FROM artifact_regions
                WHERE region =
                      'unknown_machine_readable'
                """
            )
            or {}
        ).get("n")
        or 0
    )

    columns = st.columns(4)

    labels = (
        "Profiled pairs",
        "Multi-region pairs",
        "File mappings",
        "Pairs with unknown artifacts",
    )

    values = (
        profiled,
        multi_region,
        mappings,
        unknown,
    )

    for column, label, value in zip(
        columns,
        labels,
        values,
        strict=True,
    ):
        column.metric(
            label,
            value,
        )

    display = dataframe.rename(
        columns={
            "region": "Region",
            "pair_count": "Pairs",
            "file_count": "Files",
            "scanned_pair_count": (
                "Pairs with scanner runs"
            ),
            "finding_pair_count": (
                "Pairs with stored findings"
            ),
            "introduced_pair_count": (
                "Pairs with introduced findings"
            ),
            "needs_review_count": (
                "Needs review"
            ),
            "introduced_yield_pct": (
                "Introduced yield %"
            ),
        }
    )

    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
    )

    if int(
        dataframe[
            "introduced_pair_count"
        ].sum()
    ) == 0:
        st.info(
            "No introduced findings are currently "
            "stored. Do not prioritise a region from "
            "this pilot until downstream scanners or "
            "manual validation produce evidence."
        )
    else:
        best = dataframe.sort_values(
            [
                "introduced_yield_pct",
                "introduced_pair_count",
                "pair_count",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        ).iloc[0]

        st.info(
            "Current pilot leader: `%s` with "
            "%s/%s introduced-finding pairs "
            "(%.2f%%)."
            % (
                best["region"],
                int(
                    best[
                        "introduced_pair_count"
                    ]
                ),
                int(best["pair_count"]),
                float(
                    best[
                        "introduced_yield_pct"
                    ]
                ),
            )
        )

def render_overview(settings) -> None:
    render_distributed_runtime(settings, compact=True)
    db = Database(settings.db_path)
    rows = db.query(OVERVIEW_QUERY)

    refresh_column, auto_column, _ = st.columns(
        [1.1, 2.5, 5.4]
    )

    if refresh_column.button(
        "Refresh status",
        width="stretch",
    ):
        st.rerun()

    auto_refresh = auto_column.toggle(
        "Auto-refresh scan status every 10 seconds",
        value=False,
        key="overview_auto_scan_refresh",
    )

    if auto_refresh:
        _auto_scan_progress(
            str(settings.db_path)
        )
    else:
        _render_scan_progress(db)

    total = len(rows)
    stages = [derive_stage(r) for r in rows]
    needs_review = stages.count("Needs review")
    clean = stages.count("Clean")
    in_progress = stages.count("Validated") + stages.count("Scanning") + stages.count("Scan blocked")
    ai_explicit = sum(1 for r in rows if ai_marker_label(r) != "No AI")
    codeql = sum(1 for r in rows if "CodeQL" in row_signal_label(r))
    secret = sum(1 for r in rows if "Secret/CI" in row_signal_label(r))
    dep = sum(1 for r in rows if "Dependency" in row_signal_label(r))
    candidate_yield = f"{(needs_review / total * 100):.1f}%" if total else "0.0%"
    cache_count = len(list(Path("data/cache/github_api").glob("*.json"))) if Path("data/cache/github_api").exists() else 0
    try:
        excluded_count = int((db.one("SELECT COUNT(*) AS n FROM excluded_cases") or {}).get("n") or 0)
    except Exception:
        excluded_count = 0

    metrics = [
        ("Valid cases", total, "Cases that passed basic validation and entered the database."),
        ("In progress", in_progress, "Valid cases that have not finished scanner checks yet."),
        ("Needs review", needs_review, "Cases with downstream evidence waiting for manual review."),
        ("Clean", clean, "Cases scanned with no promoted downstream evidence."),
        ("Candidate yield", candidate_yield, "Needs-review cases divided by valid cases."),
        ("AI explicit", ai_explicit, "Cases with direct AI/agent markers."),
        ("Excluded", excluded_count, "Retrieved items rejected before scanner checks."),
        ("Cache", cache_count, "GitHub/API objects cached locally."),
    ]
    first = "".join(_render_metric(label, value, help_text) for label, value, help_text in metrics[:5])
    second = "".join(_render_metric(label, value, help_text) for label, value, help_text in metrics[5:])
    st.markdown(f"<div class='compact-metrics'>{first}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='compact-metrics second'>{second}</div>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class='signal-strip' title='Counts by downstream evidence type.'>
  <div class='signal-strip-title'>Signals</div>
  <div class='signal-grid'>
    <div class='signal-mini codeql'><div class='name'>CodeQL</div><div class='count'>{codeql}</div></div>
    <div class='signal-mini secret'><div class='name'>Secret/CI</div><div class='count'>{secret}</div></div>
    <div class='signal-mini dep'><div class='name'>Dependency</div><div class='count'>{dep}</div></div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    selected_terms = _render_query_builder(rows)
    filtered = _apply_filters(rows, selected_terms)

    PAGE_SIZE = 30
    total_filtered = len(filtered)
    total_pages = max(
        1,
        math.ceil(
            total_filtered / PAGE_SIZE
        ),
    )

    current_page = int(
        st.session_state.get(
            "overview_page",
            0,
        )
    )

    current_page = max(
        0,
        min(
            current_page,
            total_pages - 1,
        ),
    )

    st.session_state[
        "overview_page"
    ] = current_page

    page_start = (
        current_page * PAGE_SIZE
    )

    page_end = min(
        page_start + PAGE_SIZE,
        total_filtered,
    )

    page_rows = filtered[
        page_start:page_end
    ]

    previous_column, page_column, next_column = (
        st.columns(
            [1, 3, 1]
        )
    )

    if previous_column.button(
        "Previous page",
        disabled=current_page == 0,
        width="stretch",
        key="overview_previous_page",
    ):
        st.session_state[
            "overview_page"
        ] = current_page - 1
        st.rerun()

    page_column.markdown(
        "<div style='text-align:center; padding-top:0.45rem'>"
        f"<strong>Page {current_page + 1} of {total_pages}</strong>"
        f"<br><span class='small-muted'>"
        f"Showing {page_start + 1 if total_filtered else 0}"
        f"–{page_end} of {total_filtered} cases"
        "</span></div>",
        unsafe_allow_html=True,
    )

    if next_column.button(
        "Next page",
        disabled=(
            current_page >= total_pages - 1
        ),
        width="stretch",
        key="overview_next_page",
    ):
        st.session_state[
            "overview_page"
        ] = current_page + 1
        st.rerun()

    st.markdown(f"**{total_filtered} matching cases**")
    if not filtered:
        st.info("No cases match the current filters.")
        _render_exclusion_audit(db)
        return

    st.markdown("<div class='case-table-header'><div></div><div>Case</div><div>Repo</div><div>Stage</div><div>Signal</div><div>AI marker</div><div>Indicator term</div><div>Label</div><div class='hide-small'>Review</div><div>Open</div></div>", unsafe_allow_html=True)

    selected_ids: list[int] = []
    for r in page_rows:
        case_id = int(r["case_id"])
        terms = derive_query_terms(r)
        repo = html.escape(str(r.get("repo") or ""))
        repo_url = html.escape(str(r.get("repo_url") or f"https://github.com/{r.get('repo')}"))
        stage = derive_stage(r)
        sig = row_signal_label(r)
        ai = ai_marker_label(r)
        label = display_label(r)
        priority = priority_score(r)
        review_label = "High" if priority >= 12 else "Medium" if priority >= 6 else "Normal"
        selected_key = f"case_select_{case_id}"

        cols = st.columns([.35, .65, 1.55, .85, 1, 1.25, 1.75, 1, .7, .75], gap="small", vertical_alignment="center")
        selected = cols[0].checkbox(f"Select case {case_id}", key=selected_key, label_visibility="collapsed")
        if selected:
            selected_ids.append(case_id)
        cols[1].markdown(f"**#{case_id}**")
        cols[2].markdown(f"[{repo}]({repo_url})")
        cols[3].markdown(f"<span class='badge badge-stage'>{html.escape(stage)}</span>", unsafe_allow_html=True)
        sig_class = "badge-clean" if sig == "Clean" else "badge-signal"
        cols[4].markdown(f"<span class='badge {sig_class}'>{html.escape(sig)}</span>", unsafe_allow_html=True)
        ai_class = "badge-ai" if ai != "No AI" else "badge"
        cols[5].markdown(f"<span class='badge {ai_class}' title='Exact AI/agent indicator when present'>{html.escape(ai)}</span>", unsafe_allow_html=True)
        if terms:
            cols[6].markdown(" ".join(render_term_chip(t) for t in terms[:4]), unsafe_allow_html=True)
        else:
            cols[6].markdown("<span class='small-muted'>base only</span>", unsafe_allow_html=True)
        cols[7].markdown(html.escape(label))
        job_summary = str(r.get("scanner_job_statuses") or r.get("scanner_statuses") or "")
        if review_label == "Normal" and job_summary:
            review_label = "Done" if stage == "Clean" else review_label
        cols[8].markdown(review_label)
        if cols[9].button("Open", key=f"open_case_{case_id}", width="stretch"):
            _open_case(case_id, [int(x["case_id"]) for x in filtered])

    if selected_ids:
        st.markdown(f"**{len(selected_ids)} selected**")
        b1, b2, b3, _ = st.columns([1.2, 1.7, 1, 3])
        if b1.button("Review selected", type="primary", width="stretch"):
            _open_case(selected_ids[0], selected_ids)
        b2.download_button(
            "Export selected evidence ZIP",
            data=selected_evidence_zip(db, selected_ids),
            file_name="selected_cases_evidence.zip",
            mime="application/zip",
            width="stretch",
        )
        if b3.button("Clear selection", width="stretch"):
            for cid in selected_ids:
                st.session_state.pop(f"case_select_{cid}", None)
            st.rerun()
    else:
        best_ids = _best_case_ids(filtered)
        b1, _ = st.columns([1.3, 5])
        if best_ids and b1.button("Review best cases", type="primary", width="stretch", help="Opens visible needs-review cases ordered by review priority."):
            _open_case(best_ids[0], best_ids)


    _render_exclusion_audit(db)
    _render_region_yield_panel(db)
