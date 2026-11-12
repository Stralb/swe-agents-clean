from __future__ import annotations

from miner.db.database import Database

TERMINAL_OK = {"ok", "done", "not_applicable", "ok_with_warnings"}
ACTIVE_OR_BAD = {"pending", "retry", "running", "error", "timeout", "partial", "tool_missing", "parse_failed"}


def sync_case_statuses(db: Database) -> None:
    """Make cases.status reflect current scanner_jobs and introduced findings.

    This is deliberately based on scanner_jobs, not stale historical scanner_runs,
    so reruns/repairs cannot leave completed cases marked as still needing
    scanning.
    """
    cases = db.query("SELECT id FROM cases WHERE status NOT IN ('reviewed','excluded') ORDER BY id")
    for row in cases:
        case_id = int(row["id"])
        finding_count = int((db.one("SELECT COUNT(*) AS n FROM scanner_findings WHERE case_id=? AND introduced=1", (case_id,)) or {"n": 0}).get("n") or 0)
        if finding_count > 0:
            db.execute(
                "UPDATE cases SET status='needs_review', downstream_signal='vulnerability', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (case_id,),
            )
            continue
        jobs = db.query("SELECT job_type,status FROM scanner_jobs WHERE case_id=?", (case_id,))
        if not jobs:
            db.execute("UPDATE cases SET status='metadata_collected', downstream_signal=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
            continue
        statuses = {str(j["status"] or "") for j in jobs}
        if statuses & {"pending", "retry", "running"}:
            db.execute("UPDATE cases SET status='scanner_running', downstream_signal=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
        elif statuses & {"error", "timeout", "partial", "tool_missing", "parse_failed"}:
            db.execute("UPDATE cases SET status='scan_blocked', downstream_signal='scanner_error', updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
        elif statuses <= TERMINAL_OK:
            if any(str(j["status"] or "") == "not_applicable" for j in jobs):
                db.execute("UPDATE cases SET status='scan_blocked', downstream_signal='not_applicable', updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
            else:
                db.execute("UPDATE cases SET status='scanned_clean', downstream_signal='no_introduced_finding', updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
        else:
            db.execute("UPDATE cases SET status='scanner_running', downstream_signal=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (case_id,))
