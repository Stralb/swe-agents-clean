from pathlib import Path

root = Path.cwd()
overview_path = root / "ui/views/overview.py"
case_path = root / "ui/views/case_review.py"

for path in (overview_path, case_path):
    if not path.exists():
        raise SystemExit(f"Missing required file: {path}")

# ------------------------------------------------------------------
# Overview: live scanner progress + multi-label region summary.
# ------------------------------------------------------------------
overview = overview_path.read_text(encoding="utf-8")
if "def _scan_progress_data" in overview:
    raise SystemExit("Step 2 already appears to be applied")

progress_code = r'''

CHEAP_SCANNERS = ("gitleaks", "dependency-diff", "osv-scanner", "semgrep")
TRACKED_SCANNERS = CHEAP_SCANNERS + ("codeql",)
TERMINAL_STATUSES = {
    "ok", "finding", "not_applicable", "skipped", "complete", "completed",
    "error", "timeout", "tool_missing", "partial",
}
ERROR_STATUSES = {"error", "timeout", "tool_missing", "partial"}


def _scan_progress_data(db: Database) -> tuple[dict, pd.DataFrame]:
    case_ids = [int(row["id"]) for row in db.query("SELECT id FROM cases ORDER BY id")]
    total = len(case_ids)
    latest = db.query(
        """
        SELECT sr.case_id, sr.scanner, sr.status, sr.started_at, sr.finished_at
        FROM scanner_runs sr
        JOIN (
            SELECT case_id, scanner, MAX(id) AS max_id
            FROM scanner_runs
            WHERE case_id IS NOT NULL
            GROUP BY case_id, scanner
        ) picked ON picked.max_id=sr.id
        WHERE sr.scanner IN ('gitleaks','dependency-diff','osv-scanner','semgrep','codeql')
        """
    )

    status_by_case: dict[int, dict[str, str]] = {}
    for row in latest:
        status_by_case.setdefault(int(row["case_id"]), {})[str(row["scanner"])] = str(row["status"] or "unknown")

    cheap_finished = 0
    problem_cases = 0
    codeql_finished = 0
    for case_id in case_ids:
        states = status_by_case.get(case_id, {})
        if all(states.get(scanner) in TERMINAL_STATUSES for scanner in CHEAP_SCANNERS):
            cheap_finished += 1
        if states.get("codeql") in TERMINAL_STATUSES:
            codeql_finished += 1
        if any(status in ERROR_STATUSES for status in states.values()):
            problem_cases += 1

    rows = []
    for scanner in TRACKED_SCANNERS:
        states = [case.get(scanner) for case in status_by_case.values() if scanner in case]
        finished = sum(status in TERMINAL_STATUSES for status in states)
        rows.append({
            "Scanner": scanner,
            "Finished": f"{finished}/{total}",
            "Progress %": round((finished / total * 100), 1) if total else 0.0,
            "OK": states.count("ok"),
            "Not applicable": states.count("not_applicable"),
            "Running": states.count("running"),
            "Errors": sum(status in ERROR_STATUSES for status in states),
            "No terminal result": max(0, total - finished),
        })

    active_jobs = int((db.one(
        "SELECT COUNT(*) AS n FROM scanner_jobs WHERE status IN ('pending','retry','running')"
    ) or {}).get("n") or 0)
    last_activity = (db.one(
        """
        SELECT MAX(ts) AS ts FROM (
            SELECT MAX(COALESCE(finished_at, started_at)) AS ts FROM scanner_runs
            UNION ALL
            SELECT MAX(COALESCE(finished_at, started_at, created_at)) AS ts FROM scanner_jobs
            UNION ALL
            SELECT MAX(updated_at) AS ts FROM cases
        )
        """
    ) or {}).get("ts") or "no recorded activity"

    summary = {
        "total": total,
        "cheap_finished": cheap_finished,
        "codeql_finished": codeql_finished,
        "problem_cases": problem_cases,
        "active_jobs": active_jobs,
        "findings": int((db.one("SELECT COUNT(*) AS n FROM scanner_findings") or {}).get("n") or 0),
        "introduced": int((db.one(
            "SELECT COUNT(*) AS n FROM scanner_findings WHERE COALESCE(introduced,0)=1"
        ) or {}).get("n") or 0),
        "last_activity": last_activity,
    }
    return summary, pd.DataFrame(rows)


def _render_scan_progress(db: Database) -> None:
    summary, table = _scan_progress_data(db)
    total = summary["total"]
    st.markdown("### Scan progress")
    st.caption(
        "Based on the latest case-level run for each scanner. `not_applicable` counts as "
        "finished; failures are shown separately."
    )
    values = [
        ("Cheap scans finished", f"{summary['cheap_finished']}/{total}"),
        ("Cheap scans pending", max(0, total - summary["cheap_finished"])),
        ("CodeQL finished", f"{summary['codeql_finished']}/{total}"),
        ("CodeQL pending", max(0, total - summary["codeql_finished"])),
        ("Cases with scan problems", summary["problem_cases"]),
        ("Active queued jobs", summary["active_jobs"]),
        ("Stored findings", summary["findings"]),
        ("Introduced findings", summary["introduced"]),
    ]
    cols = st.columns(4)
    for index, (label, value) in enumerate(values):
        cols[index % 4].metric(label, value)
    st.progress(
        summary["cheap_finished"] / total if total else 0.0,
        text=f"Cheap scanner coverage: {summary['cheap_finished']}/{total}",
    )
    st.progress(
        summary["codeql_finished"] / total if total else 0.0,
        text=f"CodeQL aggregate coverage: {summary['codeql_finished']}/{total}",
    )
    st.caption(f"Last database activity: `{summary['last_activity']}`")
    with st.expander("Per-scanner status", expanded=True):
        st.dataframe(table, hide_index=True, use_container_width=True)


if hasattr(st, "fragment"):
    @st.fragment(run_every="10s")
    def _auto_scan_progress(db_path: str) -> None:
        _render_scan_progress(Database(Path(db_path)))
else:
    def _auto_scan_progress(db_path: str) -> None:
        _render_scan_progress(Database(Path(db_path)))
'''

anchor = "\n\ndef _region_yield_dataframe(db: Database) -> pd.DataFrame:\n"
if anchor not in overview:
    raise SystemExit("Overview region-function anchor not found")
overview = overview.replace(anchor, progress_code + anchor, 1)

start = overview.index("def _region_yield_dataframe(db: Database) -> pd.DataFrame:\n")
end = overview.index("\ndef render_overview(settings) -> None:\n", start)
region_code = r'''def _region_yield_dataframe(db: Database) -> pd.DataFrame:
    rows = db.query(
        """
        WITH memberships AS (
            SELECT DISTINCT case_id, region
            FROM artifact_regions
        ), file_counts AS (
            SELECT region, COUNT(*) AS files
            FROM artifact_regions
            GROUP BY region
        )
        SELECT
            m.region,
            COUNT(DISTINCT m.case_id) AS pair_count,
            MAX(fc.files) AS file_count,
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1 FROM scanner_runs sr WHERE sr.case_id=m.case_id
            ) THEN m.case_id END) AS scanned_pair_count,
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1 FROM scanner_findings sf WHERE sf.case_id=m.case_id
            ) THEN m.case_id END) AS finding_pair_count,
            COUNT(DISTINCT CASE WHEN EXISTS (
                SELECT 1 FROM scanner_findings sf
                WHERE sf.case_id=m.case_id AND COALESCE(sf.introduced,0)=1
            ) THEN m.case_id END) AS introduced_pair_count,
            COUNT(DISTINCT CASE WHEN c.status='needs_review' THEN m.case_id END) AS needs_review_count
        FROM memberships m
        JOIN cases c ON c.id=m.case_id
        JOIN file_counts fc ON fc.region=m.region
        GROUP BY m.region
        ORDER BY introduced_pair_count DESC, pair_count DESC, m.region
        """
    )
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    for column in (
        "pair_count", "file_count", "scanned_pair_count", "finding_pair_count",
        "introduced_pair_count", "needs_review_count",
    ):
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    df["introduced_yield_pct"] = df.apply(
        lambda row: round(row["introduced_pair_count"] / row["pair_count"] * 100, 2)
        if row["pair_count"] else 0.0,
        axis=1,
    )
    return df


def _render_region_yield_panel(db: Database) -> None:
    st.markdown("---")
    st.subheader("Artifact-region coverage and yield")
    st.caption(
        "Multi-label view: a pair can appear in several regions. Regions route analysis; "
        "they do not determine whether a pair is malicious."
    )
    df = _region_yield_dataframe(db)
    if df.empty:
        st.info("No persisted artifact-region mappings are available yet.")
        return

    profiled = int((db.one("SELECT COUNT(DISTINCT case_id) AS n FROM artifact_regions") or {}).get("n") or 0)
    mappings = int((db.one("SELECT COUNT(*) AS n FROM artifact_regions") or {}).get("n") or 0)
    multi = int((db.one(
        """
        SELECT COUNT(*) AS n FROM (
            SELECT case_id FROM artifact_regions
            GROUP BY case_id HAVING COUNT(DISTINCT region)>1
        )
        """
    ) or {}).get("n") or 0)
    unknown = int((db.one(
        "SELECT COUNT(DISTINCT case_id) AS n FROM artifact_regions WHERE region='unknown_machine_readable'"
    ) or {}).get("n") or 0)

    cols = st.columns(4)
    for col, label, value in zip(
        cols,
        ("Profiled pairs", "Multi-region pairs", "File mappings", "Pairs with unknown artifacts"),
        (profiled, multi, mappings, unknown),
    ):
        col.metric(label, value)

    display = df.rename(columns={
        "region": "Region",
        "pair_count": "Pairs",
        "file_count": "Files",
        "scanned_pair_count": "Pairs with scanner runs",
        "finding_pair_count": "Pairs with stored findings",
        "introduced_pair_count": "Pairs with introduced findings",
        "needs_review_count": "Needs review",
        "introduced_yield_pct": "Introduced yield %",
    })
    st.dataframe(display, hide_index=True, use_container_width=True)

    if int(df["introduced_pair_count"].sum()) == 0:
        st.info(
            "No introduced findings are stored yet. Do not prioritise a region from this pilot "
            "until the scanners and manual validation produce downstream evidence."
        )
    else:
        best = df.sort_values(
            ["introduced_yield_pct", "introduced_pair_count", "pair_count"],
            ascending=[False, False, False],
        ).iloc[0]
        st.info(
            f"Current pilot leader: `{best['region']}` with "
            f"{int(best['introduced_pair_count'])}/{int(best['pair_count'])} introduced-finding pairs "
            f"({float(best['introduced_yield_pct']):.2f}%)."
        )

'''
overview = overview[:start] + region_code + overview[end + 1:]

render_anchor = "    rows = db.query(OVERVIEW_QUERY)\n\n"
render_insert = '''    rows = db.query(OVERVIEW_QUERY)\n\n    refresh_col, auto_col, _ = st.columns([1.1, 2.3, 5.6])\n    if refresh_col.button("Refresh status", use_container_width=True):\n        st.rerun()\n    auto_refresh = auto_col.toggle(\n        "Auto-refresh scan status every 10 seconds",\n        value=False,\n        key="overview_auto_scan_refresh",\n    )\n    if auto_refresh:\n        _auto_scan_progress(str(settings.db_path))\n    else:\n        _render_scan_progress(db)\n\n'''
if render_anchor not in overview:
    raise SystemExit("Overview render anchor not found")
overview = overview.replace(render_anchor, render_insert, 1)
overview_path.write_text(overview, encoding="utf-8")

# ------------------------------------------------------------------
# Case review: add multi-label region evidence at bottom of Downstream.
# ------------------------------------------------------------------
case = case_path.read_text(encoding="utf-8")
if "def _render_region_mapping" in case:
    raise SystemExit("Case-review Step 2 already appears to be applied")

case = case.replace("import html\n", "import html\nimport json\n", 1)

helper_anchor = "\n\ndef render_case_review(settings) -> None:\n"
helper = r'''

ROUTE_TO_SCANNER = {
    "semgrep_source": "semgrep",
    "semgrep_script": "semgrep",
    "codeql": "codeql",
    "dependency_downgrade": "dependency-diff",
    "osv_dependency": "osv-scanner",
    "secret_ci": "gitleaks",
    "trivy": "trivy",
    "trivy_vuln": "trivy",
    "trivy_secret": "trivy",
    "trivy_misconfig": "trivy",
}


def _route_list(value: str | None) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
    except Exception:
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def _render_region_mapping(profile: dict | None, rows: list[dict], scanner_runs: list[dict]) -> None:
    st.markdown("---")
    st.markdown("#### Artifact-region mapping")
    st.caption(
        "Versioned, multi-label routing evidence. A region describes the touched artifact; "
        "it is not a maliciousness decision."
    )
    if not rows:
        st.warning(
            "UNMAPPED: no region record exists for this pair. This differs from "
            "`unknown_machine_readable`, where the mapper ran but lacked a specific category."
        )
        return

    regions = sorted({str(row.get("region") or "unknown") for row in rows})
    versions = sorted({str(row.get("mapping_version") or "unknown") for row in rows})
    unknown = sum(row.get("region") == "unknown_machine_readable" for row in rows)
    cols = st.columns(4)
    cols[0].metric("Regions", len(regions))
    cols[1].metric("Mapped files", len(rows))
    cols[2].metric("Unknown artifacts", unknown)
    cols[3].metric("Mapping version", ", ".join(versions))
    st.markdown("**Pair regions:** " + " ".join(f"`{region}`" for region in regions))
    st.caption(
        "Compatibility summary: `" + str((profile or {}).get("primary_region") or "not stored")
        + "`. This field is not an exclusive scientific label."
    )

    latest = {}
    for run in scanner_runs:
        latest.setdefault(str(run.get("scanner") or "unknown"), str(run.get("status") or "unknown"))

    details = []
    for row in rows:
        routes = _route_list(row.get("scanner_routes"))
        observed = []
        for route in routes:
            scanner = ROUTE_TO_SCANNER.get(route)
            observed.append(
                f"{route} -> {scanner}:{latest.get(scanner, 'not run')}"
                if scanner else f"{route} -> not implemented/stored"
            )
        details.append({
            "Path": row.get("path"),
            "Region": row.get("region"),
            "Language": row.get("language") or "",
            "Confidence": row.get("confidence") or "",
            "Reason": row.get("evidence") or "",
            "Planned routes": ", ".join(routes) or "none",
            "Observed scanner state": "; ".join(observed) or "none",
        })
    st.dataframe(details, hide_index=True, use_container_width=True)
    if unknown:
        st.warning(
            f"{unknown} artifact(s) are `unknown_machine_readable`; inspect these when refining the taxonomy."
        )
'''
if helper_anchor not in case:
    raise SystemExit("Case-review helper anchor not found")
case = case.replace(helper_anchor, helper + helper_anchor, 1)

jobs_anchor = '    scanner_jobs = db.query("SELECT job_type, status, priority, route_reason, last_error, worker_id, started_at, finished_at FROM scanner_jobs WHERE case_id=? ORDER BY job_type", (case_id,))\n'
queries = jobs_anchor + '''    region_profile = db.one(\n        """\n        SELECT primary_region, mapping_version, file_count, updated_at\n        FROM pr_region_profiles WHERE case_id=?\n        """,\n        (case_id,),\n    )\n    region_rows = db.query(\n        """\n        SELECT path, region, language, scanner_routes, confidence, evidence, mapping_version\n        FROM artifact_regions WHERE case_id=?\n        ORDER BY region, path\n        """,\n        (case_id,),\n    )\n'''
if jobs_anchor not in case:
    raise SystemExit("Case-review scanner-jobs anchor not found")
case = case.replace(jobs_anchor, queries, 1)

old_call = "    with tab_downstream:\n        render_downstream_panel(row, files, findings, scanner_runs, scanner_jobs)\n"
new_call = "    with tab_downstream:\n        render_downstream_panel(row, files, findings, scanner_runs, scanner_jobs)\n        _render_region_mapping(region_profile, region_rows, scanner_runs)\n"
if old_call not in case:
    raise SystemExit("Case-review downstream anchor not found")
case = case.replace(old_call, new_call, 1)
case_path.write_text(case, encoding="utf-8")

print("Step 2 UI patch applied")
