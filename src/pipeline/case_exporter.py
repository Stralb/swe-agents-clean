from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from src.db.database import Database

CASE_QUERY = """
SELECT
    c.id AS case_id,
    c.ai_cohort,
    c.downstream_signal,
    c.auto_tags,
    c.status,
    c.final_label,
    c.review_notes,
    c.created_at AS case_created_at,
    c.updated_at AS case_updated_at,
    r.id AS repo_id,
    r.full_name AS repo,
    r.html_url AS repo_url,
    r.stars AS repo_stars,
    r.language AS repo_language,
    i.id AS issue_id,
    i.number AS issue_number,
    i.url AS issue_url,
    i.title AS issue_title,
    i.body AS issue_body,
    i.author AS issue_author,
    i.state AS issue_state,
    i.labels AS issue_labels,
    i.comments_count AS issue_comments_count,
    i.created_at AS issue_created_at,
    i.updated_at AS issue_updated_at,
    i.closed_at AS issue_closed_at,
    i.word_count AS issue_word_count,
    i.is_english AS issue_is_english,
    p.id AS pr_id,
    p.number AS pr_number,
    p.url AS pr_url,
    p.title AS pr_title,
    p.body AS pr_body,
    p.author AS pr_author,
    p.state AS pr_state,
    p.merged AS pr_merged,
    p.head_ref,
    p.base_ref,
    p.head_sha,
    p.base_sha,
    p.additions,
    p.deletions,
    p.changed_files_count,
    p.commits_count,
    p.review_comments_count,
    p.created_at AS pr_created_at,
    p.updated_at AS pr_updated_at,
    p.closed_at AS pr_closed_at,
    p.merged_at AS pr_merged_at,
    uf.has_code_block,
    uf.has_inline_code,
    uf.has_traceback_or_log,
    uf.has_file_path,
    uf.has_function_or_class,
    uf.has_dependency_or_version,
    uf.has_suggested_fix,
    uf.has_ai_marker,
    uf.feature_json
FROM cases c
JOIN repos r ON c.repo_id = r.id
JOIN issues i ON c.issue_id = i.id
JOIN pull_requests p ON c.pr_id = p.id
LEFT JOIN upstream_features uf ON uf.issue_id = i.id
WHERE c.id=?
"""

SUMMARY_QUERY = """
SELECT
    c.id AS case_id,
    r.full_name AS repo,
    i.title AS issue_title,
    i.url AS issue_url,
    p.title AS pr_title,
    p.url AS pr_url,
    c.ai_cohort,
    c.downstream_signal,
    c.auto_tags,
    c.final_label,
    c.status,
    c.review_notes,
    COALESCE((SELECT COUNT(*) FROM scanner_findings sf WHERE sf.case_id=c.id), 0) AS finding_count,
    COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM case_tags ct JOIN tags t ON ct.tag_id=t.id WHERE ct.case_id=c.id), '') AS manual_tags
FROM cases c
JOIN repos r ON c.repo_id = r.id
JOIN issues i ON c.issue_id = i.id
JOIN pull_requests p ON c.pr_id = p.id
WHERE c.id IN ({placeholders})
ORDER BY c.id DESC
"""


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _clean_id(value: Any) -> str:
    return str(value).replace("/", "_").replace("\\", "_").replace(" ", "_")


def get_case_evidence(db: Database, case_id: int) -> dict[str, Any]:
    row = db.one(CASE_QUERY, (case_id,))
    if not row:
        raise ValueError(f"Case {case_id} not found")

    files = db.query(
        """
        SELECT filename, category, status, additions, deletions, patch
        FROM pr_files
        WHERE pr_id=?
        ORDER BY category, filename
        """,
        (row["pr_id"],),
    )
    findings = db.query(
        """
        SELECT scanner, finding_type, severity, rule_id, cwe, file_path, line, description, evidence, raw_json, introduced, created_at
        FROM scanner_findings
        WHERE case_id=?
        ORDER BY finding_type, scanner, file_path
        """,
        (case_id,),
    )
    ai_markers = db.query(
        """
        SELECT marker_text, marker_location, confidence, matched_tool, created_at
        FROM ai_markers
        WHERE case_id=? OR issue_id=? OR pr_id=?
        ORDER BY confidence, marker_location
        """,
        (case_id, row["issue_id"], row["pr_id"]),
    )
    manual_tags = db.query(
        """
        SELECT t.name, t.type, t.description, ct.added_at
        FROM case_tags ct
        JOIN tags t ON t.id=ct.tag_id
        WHERE ct.case_id=?
        ORDER BY t.name
        """,
        (case_id,),
    )
    notes = db.query(
        "SELECT note, created_at FROM case_notes WHERE case_id=? ORDER BY created_at DESC",
        (case_id,),
    )
    links = db.query(
        "SELECT method, created_at FROM issue_pr_links WHERE issue_id=? AND pr_id=?",
        (row["issue_id"], row["pr_id"]),
    )
    scanner_runs = db.query(
        """
        SELECT scanner, status, started_at, finished_at, stdout, stderr
        FROM scanner_runs
        WHERE pr_id=?
        ORDER BY started_at DESC
        """,
        (row["pr_id"],),
    )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "case": {
            "id": row["case_id"],
            "status": row["status"],
            "ai_cohort": row["ai_cohort"],
            "downstream_signal": row["downstream_signal"],
            "auto_tags": _json_loads(row.get("auto_tags"), []),
            "manual_tags": manual_tags,
            "final_label": row["final_label"],
            "review_notes": row["review_notes"],
            "created_at": row["case_created_at"],
            "updated_at": row["case_updated_at"],
        },
        "repo": {
            "full_name": row["repo"],
            "url": row["repo_url"],
            "stars": row["repo_stars"],
            "language": row["repo_language"],
        },
        "upstream_issue": {
            "number": row["issue_number"],
            "url": row["issue_url"],
            "title": row["issue_title"],
            "body": row["issue_body"],
            "author": row["issue_author"],
            "state": row["issue_state"],
            "labels": _json_loads(row.get("issue_labels"), []),
            "comments_count": row["issue_comments_count"],
            "created_at": row["issue_created_at"],
            "updated_at": row["issue_updated_at"],
            "closed_at": row["issue_closed_at"],
            "word_count": row["issue_word_count"],
            "is_english": bool(row["issue_is_english"]),
            "features": {
                "has_code_block": bool(row.get("has_code_block")),
                "has_inline_code": bool(row.get("has_inline_code")),
                "has_traceback_or_log": bool(row.get("has_traceback_or_log")),
                "has_file_path": bool(row.get("has_file_path")),
                "has_function_or_class": bool(row.get("has_function_or_class")),
                "has_dependency_or_version": bool(row.get("has_dependency_or_version")),
                "has_suggested_fix": bool(row.get("has_suggested_fix")),
                "has_ai_marker": bool(row.get("has_ai_marker")),
                "raw": _json_loads(row.get("feature_json"), {}),
            },
        },
        "downstream_pr": {
            "number": row["pr_number"],
            "url": row["pr_url"],
            "title": row["pr_title"],
            "body": row["pr_body"],
            "author": row["pr_author"],
            "state": row["pr_state"],
            "merged": bool(row["pr_merged"]),
            "head_ref": row["head_ref"],
            "base_ref": row["base_ref"],
            "head_sha": row["head_sha"],
            "base_sha": row["base_sha"],
            "additions": row["additions"],
            "deletions": row["deletions"],
            "changed_files_count": row["changed_files_count"],
            "commits_count": row["commits_count"],
            "review_comments_count": row["review_comments_count"],
            "created_at": row["pr_created_at"],
            "updated_at": row["pr_updated_at"],
            "closed_at": row["pr_closed_at"],
            "merged_at": row["pr_merged_at"],
            "files": files,
        },
        "linking": links,
        "ai_markers": ai_markers,
        "scanner_findings": findings,
        "scanner_runs": scanner_runs,
        "case_notes": notes,
    }


def case_to_markdown(evidence: dict[str, Any]) -> str:
    case = evidence["case"]
    repo = evidence["repo"]
    issue = evidence["upstream_issue"]
    pr = evidence["downstream_pr"]
    findings = evidence.get("scanner_findings", [])
    ai_markers = evidence.get("ai_markers", [])
    manual_tags = evidence["case"].get("manual_tags", [])

    lines: list[str] = []
    lines.append(f"# Case {case['id']}: {repo['full_name']}\n")
    lines.append("## Summary\n")
    lines.append(f"- **Final label:** {case.get('final_label')}\n")
    lines.append(f"- **Status:** {case.get('status')}\n")
    lines.append(f"- **AI cohort:** {case.get('ai_cohort')}\n")
    lines.append(f"- **Downstream signal:** {case.get('downstream_signal') or 'None'}\n")
    lines.append(f"- **Auto-tags:** {', '.join(case.get('auto_tags') or []) or 'None'}\n")
    lines.append(f"- **Manual tags:** {', '.join(t.get('name', '') for t in manual_tags) or 'None'}\n")
    lines.append(f"- **Review notes:** {case.get('review_notes') or ''}\n")

    lines.append("\n## Upstream issue\n")
    lines.append(f"- **Title:** {issue.get('title')}\n")
    lines.append(f"- **URL:** {issue.get('url')}\n")
    lines.append(f"- **Author:** {issue.get('author')}\n")
    lines.append(f"- **Created:** {issue.get('created_at')}\n")
    lines.append(f"- **Closed:** {issue.get('closed_at')}\n")
    lines.append(f"- **Word count:** {issue.get('word_count')}\n")
    lines.append("\n### Issue body\n")
    lines.append("```text\n" + (issue.get("body") or "")[:20000] + "\n```\n")

    lines.append("\n## Downstream PR\n")
    lines.append(f"- **Title:** {pr.get('title')}\n")
    lines.append(f"- **URL:** {pr.get('url')}\n")
    lines.append(f"- **Author:** {pr.get('author')}\n")
    lines.append(f"- **Merged:** {pr.get('merged')}\n")
    lines.append(f"- **Changed files:** {pr.get('changed_files_count')}\n")
    lines.append(f"- **Additions/deletions:** +{pr.get('additions')} / -{pr.get('deletions')}\n")
    if pr.get("body"):
        lines.append("\n### PR body\n")
        lines.append("```text\n" + (pr.get("body") or "")[:12000] + "\n```\n")

    lines.append("\n## Changed files and patches\n")
    for f in pr.get("files", []):
        lines.append(f"\n### {f.get('filename')}\n")
        lines.append(f"- **Category:** {f.get('category')}\n")
        lines.append(f"- **Status:** {f.get('status')}\n")
        lines.append(f"- **Additions/deletions:** +{f.get('additions')} / -{f.get('deletions')}\n")
        if f.get("patch"):
            lines.append("```diff\n" + (f.get("patch") or "")[:12000] + "\n```\n")

    lines.append("\n## AI markers\n")
    if ai_markers:
        for m in ai_markers:
            lines.append(f"- `{m.get('marker_text')}` at `{m.get('marker_location')}` ({m.get('confidence')}, {m.get('matched_tool')})\n")
    else:
        lines.append("No AI marker rows stored.\n")

    lines.append("\n## Scanner findings\n")
    if findings:
        for f in findings:
            lines.append(f"\n### {f.get('finding_type')} · {f.get('scanner')} · {f.get('rule_id') or f.get('cwe') or ''}\n")
            lines.append(f"- **Severity:** {f.get('severity')}\n")
            lines.append(f"- **File:** {f.get('file_path')}:{f.get('line') or ''}\n")
            lines.append(f"- **Description:** {f.get('description')}\n")
            if f.get("evidence"):
                lines.append("```text\n" + str(f.get("evidence"))[:5000] + "\n```\n")
    else:
        lines.append("No introduced scanner findings stored.\n")

    return "".join(lines)


def selected_summary_csv(db: Database, case_ids: Iterable[int]) -> bytes:
    ids = [int(x) for x in case_ids]
    if not ids:
        return b""
    placeholders = ",".join("?" for _ in ids)
    rows = db.query(SUMMARY_QUERY.format(placeholders=placeholders), ids)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0].keys()) if rows else ["case_id"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return out.getvalue().encode("utf-8")


def selected_evidence_zip(db: Database, case_ids: Iterable[int]) -> bytes:
    """Export selected cases as a review-friendly evidence bundle.

    Structure:
      index.md / index.json
      cases/case_<id>_<repo>/report.md
      cases/case_<id>_<repo>/evidence.json
      cases/case_<id>_<repo>/issue.md
      cases/case_<id>_<repo>/pr.md
      cases/case_<id>_<repo>/patches/<n>_<filename>.diff
      cases/case_<id>_<repo>/scanner_findings.json
    """
    ids = [int(x) for x in case_ids]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        index = []
        index_md = ["# Malicious Issue Miner evidence bundle\n\n", f"Exported: {datetime.now(timezone.utc).isoformat()}\n\n"]
        for cid in ids:
            evidence = get_case_evidence(db, cid)
            repo_slug = _clean_id(evidence["repo"]["full_name"])
            base = f"cases/case_{cid}_{repo_slug}"
            issue = evidence["upstream_issue"]
            pr = evidence["downstream_pr"]
            case = evidence["case"]
            summary = {
                "case_id": cid,
                "repo": evidence["repo"]["full_name"],
                "issue_title": issue.get("title"),
                "issue_url": issue.get("url"),
                "pr_title": pr.get("title"),
                "pr_url": pr.get("url"),
                "ai_cohort": case.get("ai_cohort"),
                "downstream_signal": case.get("downstream_signal"),
                "final_label": case.get("final_label"),
                "status": case.get("status"),
            }
            index.append(summary)
            index_md.append(f"## Case {cid}: {evidence['repo']['full_name']}\n")
            index_md.append(f"- Issue: {issue.get('title')}\n")
            index_md.append(f"- PR: {pr.get('title')}\n")
            index_md.append(f"- Signal: {case.get('downstream_signal') or 'None'}\n")
            index_md.append(f"- AI: {case.get('ai_cohort')}\n")
            index_md.append(f"- Folder: `{base}/`\n\n")

            zf.writestr(f"{base}/evidence.json", json.dumps(evidence, indent=2, ensure_ascii=False))
            zf.writestr(f"{base}/report.md", case_to_markdown(evidence))
            zf.writestr(f"{base}/issue.md", f"# Upstream issue\n\nURL: {issue.get('url')}\n\n## {issue.get('title')}\n\n" + (issue.get("body") or ""))
            zf.writestr(f"{base}/pr.md", f"# Downstream PR\n\nURL: {pr.get('url')}\n\n## {pr.get('title')}\n\n" + (pr.get("body") or ""))
            zf.writestr(f"{base}/scanner_findings.json", json.dumps(evidence.get("scanner_findings", []), indent=2, ensure_ascii=False))
            for idx, f in enumerate(pr.get("files", []), start=1):
                patch = f.get("patch") or ""
                if not patch:
                    continue
                fname = _clean_id(f.get("filename") or f"file_{idx}")
                zf.writestr(f"{base}/patches/{idx:03d}_{fname}.diff", patch)
        zf.writestr("index.json", json.dumps(index, indent=2, ensure_ascii=False))
        zf.writestr("index.md", "".join(index_md))
    return buf.getvalue()


def database_export_zip(db_path: Path, *, config_path: Path | None = None, export_name: str = "miner_export", project_root: Path | None = None) -> bytes:
    """Export the current SQLite DB plus reproducibility metadata as a ZIP.

    SQLite WAL files are included when present so a live Streamlit/collector session
    can be shared without silently dropping uncheckpointed writes.
    """
    safe_name = _clean_id(export_name or "miner_export")
    root = Path(project_root or Path.cwd()).resolve()
    db_path = Path(db_path).resolve()
    buf = io.BytesIO()
    try:
        from ui.retrieval import methodology_snapshot
    except Exception:  # pragma: no cover - defensive for non-UI contexts
        methodology_snapshot = lambda: {"note": "methodology snapshot unavailable"}

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for candidate in (db_path, Path(str(db_path) + "-wal"), Path(str(db_path) + "-shm")):
            if candidate.exists():
                zf.write(candidate, f"{safe_name}/{candidate.name}")
        if config_path and Path(config_path).exists():
            zf.write(Path(config_path), f"{safe_name}/config.yml")
        zf.writestr(f"{safe_name}/methodology_snapshot.json", json.dumps(methodology_snapshot(), indent=2, ensure_ascii=False))
        zf.writestr(
            f"{safe_name}/README_EXPORT.md",
            "# Malicious Issue Miner DB export\n\n"
            f"Exported: {datetime.now(timezone.utc).isoformat()}\n\n"
            "This archive contains the SQLite database plus available WAL/SHM files, "
            "config, and the retrieval-methodology snapshot used by the UI. If evidence "
            "files exist outside SQLite, they are included under `evidence_files/`.\n",
        )
        evidence_dirs = [root / "data" / "evidence", root / "evidence"]
        for evidence_dir in evidence_dirs:
            if not evidence_dir.exists() or not evidence_dir.is_dir():
                continue
            for path in evidence_dir.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(evidence_dir)
                    zf.write(path, f"{safe_name}/evidence_files/{rel.as_posix()}")
    return buf.getvalue()
