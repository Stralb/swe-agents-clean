from __future__ import annotations

import json
from collections import defaultdict

from miner.db.database import Database
from miner.filters.tool_applicability import is_codeql_source_file

OK_RUN_STATUSES = {"ok", "ok_with_warnings", "not_applicable"}
BLOCKING_RUN_STATUSES = {"error", "timeout", "tool_missing", "parse_failed", "partial"}
JOB_OK_STATUSES = {"ok", "not_applicable"}
JOB_ACTIVE_STATUSES = {"pending", "retry", "running"}
JOB_BLOCKING_STATUSES = {"error", "timeout", "partial"}


def _signal_tags_from_findings(db: Database) -> tuple[dict[int, set[str]], dict[int, set[str]]]:
    findings = db.query(
        """
        SELECT
            case_id,
            scanner,
            finding_type
        FROM scanner_findings
        WHERE introduced=1
          AND case_id IS NOT NULL
          AND finding_type IN (
              'vulnerability',
              'secret',
              'dependency'
          )
        """
    )
    types_by_case: dict[int, set[str]] = defaultdict(set)
    scanners_by_case: dict[int, set[str]] = defaultdict(set)
    for finding in findings:
        case_id = int(finding["case_id"])
        types_by_case[case_id].add(str(finding["finding_type"] or ""))
        scanners_by_case[case_id].add(str(finding["scanner"] or ""))
    return types_by_case, scanners_by_case


def _downstream_signal(types: set[str]) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    signals: list[str] = []
    if "vulnerability" in types:
        tags.append("CodeQL alert introduced")
        signals.append("vulnerability")
    if "secret" in types:
        tags.append("Secret introduced")
        signals.append("secret")
    if "dependency" in types:
        tags.append("Dependency/OSV evidence")
        signals.append("dependency")
    if len(signals) > 1:
        tags.append("Multi-signal case")
    if signals:
        tags.append("Needs review")
    return tags, signals


def _status_from_jobs(db: Database, case_id: int) -> str | None:
    jobs = db.query("SELECT job_type, status FROM scanner_jobs WHERE case_id=?", (case_id,))
    if not jobs:
        return None
    statuses = {str(job["status"] or "") for job in jobs}
    if statuses & JOB_ACTIVE_STATUSES:
        return "scanner_running"
    if statuses & JOB_BLOCKING_STATUSES:
        return "scan_blocked"
    if statuses <= JOB_OK_STATUSES:
        return "scanned_clean"
    return "scanner_running"


def _status_from_runs(db: Database, case_id: int) -> str:
    """Infer status for the legacy/direct scanner path that writes scanner_runs.

    The worker path uses scanner_jobs.  make scan currently writes scanner_runs
    directly, so the UI must not mark a case clean after only the cheap stage.
    This function treats missing applicable downstream runs as still scanning.
    """
    runs = db.query("SELECT scanner, status FROM scanner_runs WHERE case_id=?", (case_id,))
    if not runs:
        return "metadata_collected"
    run_status = {str(row["scanner"]): str(row["status"] or "") for row in runs}
    if set(run_status.values()) & BLOCKING_RUN_STATUSES:
        return "scan_blocked"

    files = db.query("SELECT pf.filename, pf.patch, pf.category FROM pr_files pf JOIN cases c ON c.pr_id=pf.pr_id WHERE c.id=?", (case_id,))
    required = {"gitleaks", "dependency-diff", "osv-scanner"}
    if any(is_codeql_source_file(str(f.get("filename") or "")) for f in files):
        required.update({"codeql-base", "codeql-head", "codeql"})
    elif any(name in run_status for name in ("codeql-base", "codeql-head", "codeql")):
        required.update({"codeql-base", "codeql-head", "codeql"})

    missing = required - set(run_status)
    if missing:
        return "scanner_running"
    if all(run_status.get(name) in OK_RUN_STATUSES for name in required):
        return "scanned_clean"
    if any(run_status.get(name) in BLOCKING_RUN_STATUSES for name in required):
        return "scan_blocked"
    return "scanner_running"


def update_case_tags_and_status(db: Database) -> None:
    """Update case tags/signals without hiding scanner progress.

    Important methodology rule: a case is clean only after every applicable
    downstream worker has a terminal ok/not_applicable result.  Findings always
    move the case to needs_review.  Missing jobs/runs remain scanner_running,
    which fixes the UI showing stale or prematurely-clean statuses during staged
    fast/full scans.
    """
    cases = db.query("SELECT id, ai_cohort, status FROM cases")
    types_by_case, _ = _signal_tags_from_findings(db)

    for case in cases:
        case_id = int(case["id"])
        current_status = str(case.get("status") or "")
        if current_status in {"reviewed", "excluded"}:
            continue

        tags = [case.get("ai_cohort") or "AI-unknown"]
        finding_tags, signal_names = _downstream_signal(types_by_case.get(case_id, set()))
        tags.extend(finding_tags)

        if signal_names:
            computed_status = "needs_review"
            downstream_signal = ", ".join(signal_names)
        else:
            downstream_signal = None
            computed_status = _status_from_jobs(db, case_id) or _status_from_runs(db, case_id)

        db.execute(
            "UPDATE cases SET auto_tags=?, downstream_signal=?, status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(sorted(set(tags))), downstream_signal, computed_status, case_id),
        )
