from __future__ import annotations

import sys
import html
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.database import Database
from src.pipeline.case_exporter import database_export_zip
from src.settings import load_settings
from ui.views.case_review import render_case_review
from ui.views.overview import render_overview
from ui.views.analytics import render_analytics_tabs
from ui.retrieval import BASE_QUERY, STREAMS, methodology_snapshot

settings = load_settings()
# Keep the UI resilient after upgrades: initialize any new tables before rendering.
Database(settings.db_path).init_schema(ROOT / "src" / "db" / "schema.sql")
st.set_page_config(page_title=settings.config.get("ui", {}).get("page_title", "Malicious Issue Miner"), layout="wide", page_icon="🛡️")

st.markdown("""
<style>
:root {
  --mim-bg:#f8fafc; --mim-card:#ffffff; --mim-text:#0f172a; --mim-muted:#64748b; --mim-border:#d9e2ef;
  --mim-blue:#2563eb; --mim-purple:#7c3aed; --mim-orange:#ea580c; --mim-red:#dc2626; --mim-green:#16a34a; --mim-yellow:#ca8a04; --mim-brown:#92400e;
  --mim-code:#0b1220; --mim-sidebar:#0f172a; --mim-sidebar-panel:#111827;
}
html, body, [class*="css"] { color: var(--mim-text); font-size: 13px; }
header[data-testid="stHeader"] { display:none !important; }
#MainMenu { visibility:hidden !important; }
footer { visibility:hidden !important; }
.stApp { background: var(--mim-bg) !important; color: var(--mim-text) !important; }
.block-container { padding-top: 2.25rem !important; padding-bottom: 1.2rem; max-width: 1480px; }
.main .block-container h1, .main .block-container h2, .main .block-container h3 { margin-top:.15rem; margin-bottom:.35rem; }
/* Sidebar: dark navigation, readable controls */
section[data-testid="stSidebar"] { background:var(--mim-sidebar) !important; border-right:1px solid #1e293b; }
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] strong,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaptionContainer,
section[data-testid="stSidebar"] [data-testid="stRadio"] p { color:#e5e7eb !important; }
section[data-testid="stSidebar"] input { color:#0f172a !important; background:#ffffff !important; }
section[data-testid="stSidebar"] .stButton button,
section[data-testid="stSidebar"] .stDownloadButton button { color:#0f172a !important; background:#f8fafc !important; border:1px solid #cbd5e1 !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] { background:#111827 !important; border:1px solid #334155 !important; border-radius:12px !important; }
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p { color:#f8fafc !important; font-weight:800 !important; }
.sidebar-db-card { border:1px solid #334155; border-radius:14px; background:#111827; padding:10px 12px; margin-top:12px; }
.sidebar-db-title { color:#f8fafc !important; font-weight:900; font-size:.9rem; margin-bottom:6px; }
.sidebar-db-line { color:#cbd5e1 !important; font-size:.76rem; margin:3px 0; }
/* Compact metrics */
.compact-metrics { display:grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap:8px; margin-bottom:8px; }
.compact-metrics.second { grid-template-columns: repeat(4, minmax(160px, 1fr)); }
.metric-mini { border:1px solid var(--mim-border); border-radius:12px; background:var(--mim-card); padding:8px 10px; min-height:58px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.signal-strip { border:1px solid var(--mim-border); border-radius:14px; background:#ffffff; padding:8px 10px; margin:0 0 10px; }
.signal-strip-title { font-size:.74rem; color:var(--mim-muted); font-weight:900; margin-bottom:6px; }
.signal-grid { display:grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap:8px; }
.signal-mini { border:1px solid var(--mim-border); border-radius:12px; background:#f8fafc; padding:7px 9px; min-height:42px; }
.signal-mini .name { font-size:.72rem; font-weight:900; color:#334155; white-space:nowrap; }
.signal-mini .count { font-size:1rem; font-weight:950; color:#0f172a; }
.signal-mini.source { border-left:4px solid var(--mim-green); }
.signal-mini.codeql { border-left:4px solid #0f766e; }
.signal-mini.secret { border-left:4px solid var(--mim-red); }
.signal-mini.dep { border-left:4px solid var(--mim-orange); }
.metric-mini .label { font-size:.72rem; color:var(--mim-muted); font-weight:800; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.metric-mini .value { font-size:1.02rem; line-height:1.24rem; font-weight:900; color:var(--mim-text); white-space:normal; overflow:visible; text-overflow:clip; word-break:normal; }
.metric-mini .hint { float:right; color:var(--mim-muted); font-size:.7rem; }
/* Query builder */
.query-panel { border:1px solid var(--mim-border); border-radius:16px; background:#fff; padding:12px; margin:8px 0 12px; }
.query-panel-title { font-size:.92rem; font-weight:900; color:#0f172a; margin-bottom:8px; }
.query-base-card { border:1px solid var(--mim-border); border-radius:12px; background:#f8fafc; padding:8px 10px; margin-bottom:10px; }
.query-base { display:inline-block; color:var(--mim-text) !important; background:#eef2f7; border:1px solid var(--mim-border); border-radius:9px; padding:4px 8px; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.76rem; }
.stream-grid { display:grid; grid-template-columns: repeat(3, minmax(260px, 1fr)); gap:10px; }
.stream-card { border:1px solid var(--mim-border); border-top:4px solid var(--stream-color,#2563eb); border-radius:14px; background:var(--mim-card); padding:10px 12px; min-height:126px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.stream-title { font-size:.86rem; font-weight:950; color:var(--stream-color,#2563eb) !important; margin-bottom:7px; }
.query-term, .query-chip-link { display:inline-block; border:1px solid currentColor; border-radius:999px; padding:3px 8px; margin:3px 4px 3px 0; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.70rem; font-weight:850; text-decoration:none !important; background:#fff; }
.query-chip-link:hover { filter:brightness(.96); transform:translateY(-1px); }
.query-chip-selected { color:#ffffff !important; background:var(--stream-color,#2563eb) !important; border-color:var(--stream-color,#2563eb) !important; }
.term-count { opacity:.72; font-family:inherit; font-weight:700; }
.active-query-box { border-left:4px solid #94a3b8; background:#f8fafc; border-radius:10px; padding:8px 10px; margin-top:8px; }
/* Controls */
.stButton button, .stDownloadButton button, .stLinkButton a { border-radius:10px !important; font-weight:750 !important; padding:.32rem .58rem !important; min-height:2rem !important; font-size:.82rem !important; }
.stTextInput input, .stSelectbox div[data-baseweb="select"] { min-height:2.05rem !important; font-size:.82rem !important; }
[data-testid="stExpander"] { background:var(--mim-card) !important; border-color:var(--mim-border) !important; border-radius:14px !important; }
[data-testid="stExpander"] details summary p { font-size:.88rem !important; font-weight:850 !important; }
div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] { gap:.45rem; }
/* Case table */
.case-table-header { display:grid; grid-template-columns: 32px 58px 1.45fr .85fr 1fr 1.18fr 1.65fr 1fr 62px 72px; gap:7px; align-items:center; font-size:.70rem; font-weight:950; color:var(--mim-muted); padding:5px 8px; border-bottom:1px solid var(--mim-border); }
.case-row { display:grid; grid-template-columns: 32px 58px 1.45fr .85fr 1fr 1.18fr 1.65fr 1fr 62px 72px; gap:7px; align-items:center; background:var(--mim-card); border:1px solid var(--mim-border); border-radius:12px; padding:6px 8px; margin:6px 0; font-size:.78rem; }
.case-row a { color:var(--mim-blue) !important; font-weight:850; text-decoration:none; }
.badge { display:inline-block; border-radius:999px; padding:2px 7px; font-size:.68rem; font-weight:850; background:#e2e8f0; color:#0f172a; white-space:nowrap; }
.badge-stage { background:#dbeafe; color:#1e40af; }
.badge-signal { background:#fef3c7; color:#92400e; }
.badge-ai { background:#ede9fe; color:#5b21b6; }
.badge-clean { background:#dcfce7; color:#166534; }
.small-muted { font-size:.80rem; color:var(--mim-muted) !important; }
/* Case review */
.review-header { border:1px solid var(--mim-border); background:#fff; border-radius:16px; padding:14px 16px; margin:0 0 10px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
.review-header-top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; }
.review-case-title { font-weight:950; font-size:1.18rem; line-height:1.25; }
.review-repo a { color:var(--mim-blue) !important; text-decoration:none; font-weight:900; }
.review-meta { display:flex; gap:6px; flex-wrap:wrap; margin-top:6px; }
.review-actions { margin:6px 0 8px; }
.diff-box { background:var(--mim-code); border:1px solid var(--mim-border); border-radius:12px; overflow:auto; padding:8px 0; max-height:720px; font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace; font-size:.78rem; line-height:1.35; }
.diff-line { white-space: pre; padding:2px 12px; color:#cbd5e1 !important; }
.diff-add { background:rgba(22,163,74,.18); color:#bbf7d0 !important; }
.diff-del { background:rgba(220,38,38,.18); color:#fecaca !important; }
.diff-hunk { background:rgba(37,99,235,.20); color:#bfdbfe !important; font-weight:700; }
.diff-file { color:#fde68a !important; font-weight:700; }
.diff-prefix { display:inline-block; width:1.2em; color:inherit !important; }
.diff-finding { display:inline-block; margin-left:12px; border:1px solid; border-radius:999px; padding:1px 7px; background:rgba(255,255,255,.08); font-size:.70rem; font-weight:850; }
.worker-panel { border:1px solid #334155; border-radius:14px; background:#111827; padding:9px 11px; margin-top:8px; }
.worker-title { color:#f8fafc !important; font-weight:900; font-size:.82rem; margin-bottom:5px; }
.worker-line { color:#dbeafe !important; font-size:.74rem; line-height:1.35; margin:2px 0; }
.decision-shell { border:1px solid var(--mim-border); background:#fff; border-radius:16px; padding:14px 16px; margin-top:4px; }
.decision-title { font-size:1.05rem; font-weight:950; color:#0f172a; margin-bottom:2px; }
.decision-help { color:var(--mim-muted); font-size:.82rem; margin-bottom:12px; }
.tag-pill { display:inline-block; border:1px solid #cbd5e1; background:#f8fafc; color:#0f172a; border-radius:999px; padding:3px 8px; margin:3px 3px 3px 0; font-size:.73rem; font-weight:800; }
@media (max-width: 1200px) {
  .stream-grid { grid-template-columns: repeat(2, minmax(240px, 1fr)); }
  .compact-metrics, .compact-metrics.second { grid-template-columns: repeat(3, minmax(120px,1fr)); }
}
@media (max-width: 900px) {
  .signal-grid { grid-template-columns: repeat(2, minmax(140px,1fr)); }
  .stream-grid { grid-template-columns: 1fr; }
  .compact-metrics, .compact-metrics.second { grid-template-columns: repeat(2, minmax(120px,1fr)); }
  .case-table-header, .case-row { grid-template-columns: 30px 54px 1.4fr .8fr .9fr 1fr 1.2fr .9fr 60px; }
  .case-table-header .hide-small, .case-row .hide-small { display:none; }
}
</style>
""", unsafe_allow_html=True)


def _sidebar_db_panel() -> None:
    db = Database(settings.db_path)
    try:
        needs = int((db.one("SELECT COUNT(*) AS n FROM cases WHERE status='needs_review'") or {}).get("n") or 0)
    except Exception:
        needs = 0
    db_name = settings.db_path.name
    lines = [
        "<div class='sidebar-db-card'>",
        "<div class='sidebar-db-title'>DB</div>",
        f"<div class='sidebar-db-line'>{html.escape(db_name)}</div>",
        f"<div class='sidebar-db-line'>Needs review: {needs}</div>",
    ]
    try:
        jobs = db.query("SELECT status, COUNT(*) AS n FROM scanner_jobs GROUP BY status ORDER BY status")
        if jobs:
            job_text = " · ".join(f"{r['status']}: {r['n']}" for r in jobs)
            lines.append(f"<div class='sidebar-db-line'>Jobs: {html.escape(job_text)}</div>")
    except Exception:
        pass
    try:
        rate = db.one("SELECT remaining, limit_value, reset_at, last_message FROM github_rate_limits ORDER BY updated_at DESC LIMIT 1")
        if rate:
            lines.append(f"<div class='sidebar-db-line'>GitHub: {rate.get('remaining')}/{rate.get('limit_value')} remaining</div>")
    except Exception:
        pass
    lines.append(f"<div class='sidebar-db-line'>Updated: {datetime.now().strftime('%H:%M')}</div>")
    lines.append("</div>")
    st.markdown("".join(lines), unsafe_allow_html=True)

    try:
        hb = db.query("SELECT worker_type, status, detail, updated_at FROM worker_heartbeats ORDER BY updated_at DESC LIMIT 3")
        if hb:
            worker_lines = ["<div class='worker-panel'><div class='worker-title'>Workers</div>"]
            for r in hb:
                wt = html.escape(str(r.get("worker_type") or "worker"))
                status = html.escape(str(r.get("status") or "unknown"))
                detail = html.escape(str(r.get("detail") or ""))
                worker_lines.append(f"<div class='worker-line'><strong>{wt}</strong>: {status}{(' — ' + detail) if detail else ''}</div>")
            worker_lines.append("</div>")
            st.markdown("".join(worker_lines), unsafe_allow_html=True)
    except Exception:
        pass

    default_name = f"miner_db_{datetime.now().strftime('%Y%m%d_%H%M')}"
    with st.expander("Download DB ZIP", expanded=False):
        st.caption("Exports the SQLite DB, config, methodology snapshot, and evidence files as a ZIP.")
        export_name = st.text_input("Export name", value=default_name, key="db_export_name")
        safe_name = export_name.strip() or default_name
        st.download_button(
            "Download ZIP",
            data=database_export_zip(settings.db_path, config_path=settings.config_path, export_name=safe_name, project_root=ROOT),
            file_name=f"{safe_name}.zip",
            mime="application/zip",
            use_container_width=True,
            help="Downloads the full run state. This is not a per-case evidence export.",
        )


def _render_settings() -> None:
    st.subheader("Settings")
    st.caption("Read-only view of the current local runtime settings.")
    st.json({
        "db_path": str(settings.db_path),
        "config_path": str(settings.config_path),
        "github_token_present": bool(settings.github_token),
        "limits": settings.limits.__dict__,
        "collection": settings.config.get("collection", {}),
        "scanners": settings.config.get("scanners", {}),
        "scan": settings.config.get("scan", {}),
    })


def _render_logs() -> None:
    st.subheader("Logs")
    db = Database(settings.db_path)
    try:
        runs = db.query("SELECT scanner, status, started_at, finished_at, substr(stderr, 1, 500) AS stderr FROM scanner_runs ORDER BY started_at DESC LIMIT 200")
        st.dataframe(runs, use_container_width=True, hide_index=True)
    except Exception as exc:
        st.info(f"No scanner logs available yet: {exc}")


def _render_methodology() -> None:
    st.subheader("Methodology")
    st.markdown("""
### New PR-first downstream-evidence methodology

**Old risk:** suspicious keywords were too close to the collection gate. That can bias the dataset toward cases that already *sound* suspicious.

**New frame:** start from ordinary merged PRs that are linked to same-repository issues, then let changed artifacts and base/head scanner deltas decide whether the PR has downstream security evidence.

```text
repo/month window
→ merged linked PRs
→ changed-file artifact profiling
→ artifact-region scanner routing
→ base/head scanner comparison
→ introduced downstream evidence
→ issue/PR text inspection later
→ manual review and region-yield measurement
```

Issue text, AI markers, and suspicious terms are now **features for analysis and ranking**, not first-pass inclusion gates.
""")
    st.markdown(f"**Structural PR frame:** `{BASE_QUERY}`")

    st.markdown("### Artifact regions")
    st.markdown("""
| Region | What it captures | Primary route |
|---|---|---|
| `source_code` | Behavioural application/source changes | Semgrep → CodeQL |
| `dependency_config` | manifests, lockfiles, package config | dependency diff → OSV → Trivy vuln |
| `ci_workflow` | GitHub Actions / CI execution surface | workflow risk → Gitleaks → Trivy misconfig |
| `secret_config` | env/config/credential-like surfaces | Gitleaks → Trivy secret |
| `deployment_iac` | Docker/Kubernetes/Terraform-like deployment material | Trivy misconfig → Checkov optional |
| `script_execution` | shell/build/install scripts | Semgrep/custom checks → Gitleaks |
| `agentic_tooling` | MCP/agent/tool execution configs | custom agent/workflow checks |
| `unknown_machine_readable` | unknown but parseable config/text/code-like files | Trivy + Gitleaks + manual sample |
| `generated_vendor` | generated/vendor/minified dependency blobs | separate low-priority bucket |
| `non_behavioral` | docs/images/prose-only changes | counted, normally not scanner-routed |
""")

    st.markdown("### Evidence labels are deliberately separated")
    st.markdown("""
`scanner_positive` ≠ `introduced_positive` ≠ `confirmed_downstream_positive` ≠ `manual_real_positive` ≠ `likely_malicious_issue`.

This separation prevents the UI from overstating scanner noise as maliciousness. The overview's region-yield panel shows where introduced evidence is coming from and therefore where the next mining pass should focus.
""")

    for row_start in range(0, len(STREAMS), 3):
        chunk = STREAMS[row_start:row_start + 3]
        cols = st.columns(len(chunk), gap="medium")
        for col, stream in zip(cols, chunk):
            with col:
                with st.container(border=True):
                    st.markdown(f"**Post-inclusion indicators: {stream.name}**")
                    for term in stream.terms[:8]:
                        st.markdown(f"- `{term}`")
    with st.expander("Full methodology snapshot", expanded=False):
        st.json(methodology_snapshot())
    st.info("Colored indicators are extracted after inclusion. They are not retrieval buckets; suspiciousness requires downstream evidence and manual review.")


with st.sidebar:
    st.markdown("**Issue Miner**")
    nav_options = ["Overview", "Case Review", "Settings", "Logs", "Methodology"]
    if "nav" not in st.session_state or st.session_state.get("nav") not in nav_options:
        st.session_state["nav"] = "Overview"
    selected = st.radio("Navigation", nav_options, index=nav_options.index(st.session_state.get("nav", "Overview")), label_visibility="collapsed")
    st.session_state["nav"] = selected
    _sidebar_db_panel()

if selected == "Overview":
    render_overview(settings)
    render_analytics_tabs(settings)
elif selected == "Case Review":
    render_case_review(settings)
elif selected == "Settings":
    _render_settings()
elif selected == "Logs":
    _render_logs()
else:
    _render_methodology()
