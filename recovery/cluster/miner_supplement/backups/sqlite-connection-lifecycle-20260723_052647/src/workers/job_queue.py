from __future__ import annotations

import copy
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from src.db.database import Database
from src.pipeline.case_builder import update_case_tags_and_status
from src.pipeline.case_status import sync_case_statuses
from src.filters.tool_applicability import route_reasons
from src.scanners.scanner_runner import scan_case
from src.settings import Settings

log = logging.getLogger(__name__)

JOB_SCANNERS = {
    "semgrep_source": ("semgrep",),
    "secret_ci": ("gitleaks",),
    "dependency_downgrade": ("dependency-diff",),
    "osv_dependency": ("osv-scanner",),
    "trivy_dependency": ("trivy-scanner",),
    "codeql_security": ("codeql-base", "codeql-head", "codeql"),
    "codeql": ("codeql-base", "codeql-head", "codeql"),
}

JOB_PRIORITY = {
    "semgrep_source": 45,
    "secret_ci": 40,
    "dependency_downgrade": 35,
    "osv_dependency": 30,
    "trivy_dependency": 28,
    "codeql_security": 12,
    "codeql": 10,
}

@dataclass(frozen=True)
class ClaimedJob:
    id: int
    case_id: int
    job_type: str
    priority: int
    attempts: int


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _case_select() -> str:
    return """
    SELECT
        c.id AS case_id,
        r.html_url AS repo_url,
        r.full_name AS repo_full_name,
        i.url AS issue_url,
        i.title AS issue_title,
        p.id AS pr_id,
        p.url AS pr_url,
        p.title AS pr_title,
        p.base_sha,
        p.head_sha
    FROM cases c
    JOIN repos r ON c.repo_id = r.id
    JOIN issues i ON c.issue_id = i.id
    JOIN pull_requests p ON c.pr_id = p.id
    WHERE c.id=?
    """


def files_for_case(db: Database, case_id: int) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT pf.*
        FROM pr_files pf
        JOIN cases c ON c.pr_id=pf.pr_id
        WHERE c.id=?
        """,
        (case_id,),
    )


REQUIRED_JOB_TYPES = ("semgrep_source", "secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency", "codeql")


def applicable_job_types(files: Iterable[dict[str, Any]], *, include_codeql: bool = True) -> list[str]:
    """Return explicit approved downstream worker jobs for every valid case.

    Jobs are created even when a worker will likely be not_applicable. That keeps
    the audit trail complete: a case becomes clean only after every approved
    downstream worker either ran or recorded an explicit not_applicable reason.
    """
    jobs = ["semgrep_source", "secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency"]
    if include_codeql:
        jobs.append("codeql")
    return jobs


def case_priority(db: Database, case_id: int, job_type: str) -> int:
    """Scheduler-only priority; not a candidate score or study signal."""
    return int(JOB_PRIORITY.get(job_type, 0))




def reset_running_jobs_on_start(db: Database, *, job_types: list[str] | None = None, reason: str = "Reset running job on evaluator restart.") -> int:
    """Move old interrupted running jobs back to pending.

    This is intentionally used by evaluate-only commands at process startup. If a
    prior worker was killed with Ctrl+C or the terminal closed, rows can remain
    stuck as running forever while new workers report idle because they only
    claim pending/retry jobs.
    """
    params: list[Any] = []
    filter_sql = ""
    if job_types:
        placeholders = ",".join("?" for _ in job_types)
        filter_sql = f" AND job_type IN ({placeholders})"
        params.extend(job_types)
    count_row = db.one(
        f"SELECT COUNT(*) AS n FROM scanner_jobs WHERE status='running' {filter_sql}",
        tuple(params),
    ) or {"n": 0}
    changed = int(count_row.get("n") or 0)
    db.execute(
        f"""
        UPDATE scanner_jobs
        SET status='pending', started_at=NULL, finished_at=NULL, worker_id=NULL,
            last_error=TRIM(COALESCE(last_error,'') || '\n' || ?)
        WHERE status='running'
        {filter_sql}
        """,
        (reason, *params),
    )
    update_case_stages(db)
    return changed


def reset_stale_jobs(db: Database, *, stale_minutes: int = 60, codeql_stale_minutes: int = 180) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_minutes)
    codeql_cutoff = datetime.now(timezone.utc) - timedelta(minutes=codeql_stale_minutes)
    db.execute(
        """
        UPDATE scanner_jobs
        SET status='pending', started_at=NULL, worker_id=NULL, last_error=COALESCE(last_error,'') || '\nReset stale running job.'
        WHERE status='running'
          AND started_at IS NOT NULL
          AND job_type != 'codeql'
          AND started_at < ?
        """,
        (cutoff.isoformat().replace("+00:00", "Z"),),
    )
    db.execute(
        """
        UPDATE scanner_jobs
        SET status='pending', started_at=NULL, worker_id=NULL, last_error=COALESCE(last_error,'') || '\nReset stale running CodeQL job.'
        WHERE status='running'
          AND started_at IS NOT NULL
          AND job_type = 'codeql'
          AND started_at < ?
        """,
        (codeql_cutoff.isoformat().replace("+00:00", "Z"),),
    )
    row = db.one("SELECT changes() AS n") or {"n": 0}
    return int(row.get("n") or 0)


def seed_scanner_jobs(db: Database, *, include_codeql: bool = True, case_ids: list[int] | None = None) -> int:
    """Create missing scanner jobs for validated cases.

    This is idempotent and safe to run continuously. It is what lets mining and
    evaluation be decoupled: as soon as a valid case appears, scanner jobs can be
    created and picked up by evaluator workers.
    """
    params: tuple[Any, ...] = tuple(case_ids or [])
    case_filter = ""
    if case_ids:
        case_filter = "AND c.id IN (%s)" % ",".join("?" for _ in case_ids)
    rows = db.query(
        f"""
        SELECT c.id AS case_id
        FROM cases c
        WHERE c.status NOT IN ('reviewed', 'excluded')
        {case_filter}
        ORDER BY c.id ASC
        """,
        params,
    )
    created = 0
    for row in rows:
        case_id = int(row["case_id"])
        files = files_for_case(db, case_id)
        routes = route_reasons(files)
        for job_type in applicable_job_types(files, include_codeql=include_codeql):
            priority = case_priority(db, case_id, job_type)
            route_reason = routes.get(job_type, "scheduled by downstream methodology")
            before = db.one("SELECT COUNT(*) AS n FROM scanner_jobs WHERE case_id=? AND job_type=?", (case_id, job_type)) or {"n": 0}
            db.execute(
                """
                INSERT OR IGNORE INTO scanner_jobs(case_id, job_type, status, priority, route_reason)
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (case_id, job_type, priority, route_reason),
            )
            after = db.one("SELECT COUNT(*) AS n FROM scanner_jobs WHERE case_id=? AND job_type=?", (case_id, job_type)) or {"n": 0}
            created += max(0, int(after.get("n") or 0) - int(before.get("n") or 0))
    update_case_stages(db)
    return created


def claim_job(db: Database, job_types: list[str], worker_id: str | None = None) -> ClaimedJob | None:
    worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
    placeholders = ",".join("?" for _ in job_types)
    def op() -> ClaimedJob | None:
        with db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                f"""
                SELECT id, case_id, job_type, priority, attempts
                FROM scanner_jobs
                WHERE status IN ('pending','retry')
                  AND job_type IN ({placeholders})
                ORDER BY priority DESC, created_at ASC, id ASC
                LIMIT 1
                """,
                tuple(job_types),
            ).fetchone()
            if row is None:
                conn.commit()
                return None
            conn.execute(
                """
                UPDATE scanner_jobs
                SET status='running', started_at=CURRENT_TIMESTAMP, worker_id=?, attempts=attempts+1
                WHERE id=?
                """,
                (worker_id, row["id"]),
            )
            conn.commit()
            return ClaimedJob(int(row["id"]), int(row["case_id"]), str(row["job_type"]), int(row["priority"] or 0), int(row["attempts"] or 0) + 1)
    return db._retry(op)


def _scanner_config_for_job(config: dict[str, Any], job_type: str) -> dict[str, Any]:
    cfg = copy.deepcopy(config)
    scanners = cfg.setdefault("scanners", {})
    scanners["gitleaks"] = job_type == "secret_ci"
    scanners["dependency_downgrade"] = job_type == "dependency_downgrade"
    scanners["osv"] = job_type == "osv_dependency"
    scanners["trivy"] = job_type == "trivy_dependency"
    scanners["semgrep"] = job_type == "semgrep_source"
    scanners["codeql"] = job_type in {"codeql", "codeql_security"}

    if job_type in {'codeql_security', 'secret_ci', 'semgrep_source', 'trivy_dependency'}:
        cache = cfg.setdefault(
            "cache",
            {},
        )

        cache["force_rescan"] = True

    return cfg


def run_scanner_job(db: Database, settings: Settings, job: ClaimedJob) -> None:
    case = db.one(_case_select(), (job.case_id,))
    if not case:
        finish_job(db, job.id, "error", "Case disappeared before scanner job could run.")
        return
    cfg = _scanner_config_for_job(settings.config, job.job_type)
    try:
        scan_case(db, case, cfg)
        job_status, detail = _job_status_from_scanner_runs(db, job.case_id, job.job_type)
        finish_job(db, job.id, job_status, detail)
    except Exception as exc:  # pragma: no cover - exercised by integration edge cases
        log.exception("Scanner job %s failed", job.id)
        finish_job(db, job.id, "error", str(exc))
        db.execute(
            "UPDATE cases SET status='error', review_notes=COALESCE(review_notes,'') || ? WHERE id=?",
            (f"\n{job.job_type} worker error: {exc}", job.case_id),
        )
    finally:
        update_case_stages(db)


def finish_job(db: Database, job_id: int, status: str, last_error: str = "") -> None:
    db.execute(
        """
        UPDATE scanner_jobs
        SET status=?, finished_at=CURRENT_TIMESTAMP, last_error=?
        WHERE id=?
        """,
        (status, last_error[:2000], job_id),
    )


def heartbeat(db: Database, worker_id: str, worker_type: str, mode: str, status: str, detail: str = "") -> None:
    db.execute(
        """
        INSERT INTO worker_heartbeats(worker_id, worker_type, mode, status, detail, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(worker_id) DO UPDATE SET
            worker_type=excluded.worker_type,
            mode=excluded.mode,
            status=excluded.status,
            detail=excluded.detail,
            updated_at=CURRENT_TIMESTAMP
        """,
        (worker_id, worker_type, mode, status, detail[:500]),
    )


def _case_has_blocking_scanner_run(db: Database, case_id: int) -> bool:
    rows = db.query("SELECT scanner, status FROM scanner_runs WHERE case_id=?", (case_id,))
    blocking = {"error", "timeout", "tool_missing", "parse_failed"}
    for row in rows:
        status = str(row.get("status") or "").lower()
        if status in blocking:
            return True
    return False


def _job_status_from_scanner_runs(db: Database, case_id: int, job_type: str):
    status = _job_status_from_runs(db, case_id, job_type)
    detail = status
    return status, detail


def _job_status_from_runs(db: Database, case_id: int, job_type: str) -> str | None:
    mapping = {
        "semgrep_source": ["semgrep"],
        "secret_ci": ["gitleaks"],
        "dependency_downgrade": ["dependency-diff"],
        "osv_dependency": ["osv-scanner"],
        "trivy_dependency": ["trivy-scanner"],
        "codeql_security": ["codeql-base", "codeql-head", "codeql"],
        "codeql": ["codeql-base", "codeql-head", "codeql"],
    }
    scanners = mapping.get(job_type, [])
    if not scanners:
        return None
    placeholders = ",".join("?" for _ in scanners)
    runs = db.query(
        f"SELECT scanner, status FROM scanner_runs WHERE case_id=? AND scanner IN ({placeholders})",
        (case_id, *scanners),
    )
    if not runs:
        return None
    statuses = {str(r["scanner"]): str(r["status"] or "") for r in runs}
    if any(statuses.get(scanner) in {"error", "tool_missing", "parse_failed", "partial"} for scanner in scanners if scanner in statuses):
        return "error"
    if any(statuses.get(scanner) == "timeout" for scanner in scanners if scanner in statuses):
        return "timeout"
    if all(scanner in statuses and statuses[scanner] == "not_applicable" for scanner in scanners):
        return "not_applicable"
    if all(scanner in statuses and statuses[scanner] in {"ok", "ok_with_warnings", "not_applicable"} for scanner in scanners):
        return "ok"
    return None


def sync_jobs_from_scanner_runs(db: Database, case_id: int) -> None:
    """Mirror direct make-scan scanner_runs into scanner_jobs for the UI.

    The cluster/evaluator path updates scanner_jobs directly.  The synchronous
    make scan path writes scanner_runs, so this bridge keeps the overview and
    review UI accurate without changing the scanner implementation.
    """
    jobs = db.query("SELECT id, job_type, status FROM scanner_jobs WHERE case_id=?", (case_id,))
    for job in jobs:
        current = str(job["status"] or "")
        if current in {"ok", "not_applicable", "error", "timeout"}:
            continue
        mapped = _job_status_from_runs(db, case_id, str(job["job_type"] or ""))
        if mapped:
            db.execute(
                "UPDATE scanner_jobs SET status=?, finished_at=CURRENT_TIMESTAMP WHERE id=?",
                (mapped, int(job["id"])),
            )

def update_case_stages(db: Database) -> None:
    """Keep case.status aligned with current scanner_jobs.

    The old implementation mixed historical scanner_runs with current jobs, which
    left repaired/rerun cases stuck as scanner_running or scan_blocked in the UI.
    This delegates to the job-table source of truth while preserving tag updates.
    """
    update_case_tags_and_status(db)
    sync_case_statuses(db)



def seed_codeql_security_jobs(
    db: Database,
    *,
    case_ids: list[int] | None = None,
) -> int:
    """Create isolated security-only CodeQL jobs.

    Legacy ``codeql`` jobs are never changed or resumed.
    """

    before_rows = db.query(
        """
        SELECT COUNT(*) AS n
        FROM scanner_jobs
        WHERE job_type='codeql_security'
        """
    )
    before = int(before_rows[0]["n"]) if before_rows else 0

    parameters: tuple[Any, ...] = tuple(case_ids or [])
    case_filter = ""

    if case_ids:
        placeholders = ",".join("?" for _ in case_ids)
        case_filter = f"WHERE c.id IN ({placeholders})"

    cases = db.query(
        f"""
        SELECT c.id AS case_id
        FROM cases c
        {case_filter}
        ORDER BY c.id
        """,
        parameters,
    )

    supported_extensions = {
        ".c", ".cc", ".cpp", ".cxx",
        ".cs",
        ".go",
        ".h", ".hpp",
        ".java",
        ".js", ".jsx", ".mjs", ".cjs",
        ".kt", ".kts",
        ".py",
        ".rb",
        ".ts", ".tsx",
    }

    for case in cases:
        case_id = int(case["case_id"])
        files = files_for_case(db, case_id)

        supported = []

        for file_row in files:
            filename = str(
                file_row.get("filename")
                or file_row.get("path")
                or ""
            )

            if Path(filename).suffix.lower() in supported_extensions:
                supported.append(filename)

        if not supported:
            continue

        reason = (
            "Security-only CodeQL route: "
            + ", ".join(supported[:8])
        )

        db.execute(
            """
            INSERT OR IGNORE INTO scanner_jobs(
                case_id,
                job_type,
                status,
                priority,
                route_reason
            )
            VALUES (
                ?,
                'codeql_security',
                'pending',
                ?,
                ?
            )
            """,
            (
                case_id,
                JOB_PRIORITY["codeql_security"],
                reason,
            ),
        )

    after_rows = db.query(
        """
        SELECT COUNT(*) AS n
        FROM scanner_jobs
        WHERE job_type='codeql_security'
        """
    )
    after = int(after_rows[0]["n"]) if after_rows else 0

    return max(0, after - before)
