from __future__ import annotations

import logging
import time
from copy import deepcopy
from typing import Any

from src.db.database import Database
from src.pipeline.case_builder import update_case_tags_and_status
from src.workers.job_queue import seed_scanner_jobs, sync_jobs_from_scanner_runs, update_case_stages
from src.scanners.scanner_runner import scan_case
from src.settings import Settings

log = logging.getLogger(__name__)


BASE_CASE_SELECT = """
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
WHERE c.status NOT IN ('reviewed', 'excluded')
{scope_filter}
{extra_filter}
ORDER BY c.id ASC
LIMIT ?
"""


def _scope_filter(settings: Settings) -> str:
    # SCOPE=ai remains available as a narrow marker-positive cohort scan.
    # The recommended methodology is SCOPE=all, then filter/rank by agentic markers in the UI.
    return "AND c.ai_cohort != 'AI-unknown'" if settings.config.get("scan", {}).get("ai_only", False) else ""


def _enabled_cheap(scanners_cfg: dict[str, Any]) -> list[str]:
    names: list[str] = []
    if scanners_cfg.get("gitleaks", True):
        names.append("gitleaks")
    if scanners_cfg.get("dependency_downgrade", True):
        names.append("dependency-diff")
    if scanners_cfg.get("osv", True):
        names.append("osv-scanner")
    return names


def _missing_any_runs_condition(scanner_names: list[str]) -> str:
    if not scanner_names:
        return ""
    parts = [
        "NOT EXISTS (SELECT 1 FROM scanner_runs sr WHERE sr.case_id=c.id AND sr.scanner='%s')" % name.replace("'", "''")
        for name in scanner_names
    ]
    return "AND (" + " OR ".join(parts) + ")"


def _has_all_runs_condition(scanner_names: list[str]) -> str:
    if not scanner_names:
        return ""
    parts = [
        "EXISTS (SELECT 1 FROM scanner_runs sr WHERE sr.case_id=c.id AND sr.scanner='%s')" % name.replace("'", "''")
        for name in scanner_names
    ]
    return "AND " + " AND ".join(parts)


def _missing_codeql_condition() -> str:
    # CodeQL snapshot diff is represented by base/head runs. A skipped/error run still counts
    # as attempted so the scheduler does not retry forever unless FORCE_RESCAN=true.
    return """
AND (
    NOT EXISTS (SELECT 1 FROM scanner_runs sr WHERE sr.case_id=c.id AND sr.scanner='codeql-base')
    OR NOT EXISTS (SELECT 1 FROM scanner_runs sr WHERE sr.case_id=c.id AND sr.scanner='codeql-head')
    OR NOT EXISTS (SELECT 1 FROM scanner_runs sr WHERE sr.case_id=c.id AND sr.scanner='codeql')
)
"""



def _codeql_trigger_condition(scanners_cfg: dict[str, Any]) -> str:
    trigger = str(scanners_cfg.get("codeql_trigger", "all_python") or "all_python").lower()
    if trigger in {"all_python", "all", "none"}:
        return ""
    return ""

def _query_cases(db: Database, settings: Settings, extra_filter: str, limit: int) -> list[dict[str, Any]]:
    sql = BASE_CASE_SELECT.format(scope_filter=_scope_filter(settings), extra_filter=extra_filter)
    return db.query(sql, (limit,))


def _stage_config(config: dict[str, Any], *, codeql: bool, cheap: bool) -> dict[str, Any]:
    cfg = deepcopy(config)
    scanners = cfg.setdefault("scanners", {})
    scanners["codeql"] = bool(codeql)
    scanners["semgrep"] = False
    if not cheap:
        scanners["gitleaks"] = False
        scanners["osv"] = False
        scanners["dependency_downgrade"] = False
    return cfg


def _run_case(db: Database, case: dict[str, Any], config: dict[str, Any], label: str) -> None:
    log.info("%s case %s", label, case["case_id"])
    scan_case(db, case, config)
    sync_jobs_from_scanner_runs(db, int(case["case_id"]))
    update_case_tags_and_status(db)


def scan(settings: Settings) -> None:
    """Run the scanner scheduler.

    Default full mode is intentionally staged:
      1. Run cheap established scanners over the DB first: Gitleaks and dependency diff/OSV.
      2. Then run expensive CodeQL gradually.
      3. Before each new CodeQL case, check whether any newly collected case still needs cheap scans.
         If yes, switch back to cheap scans after the current CodeQL case finishes.

    This matches the research workflow: broad downstream triage first, then slower CodeQL enrichment.
    """
    db = Database(settings.db_path)
    start = time.time()
    touched = 0

    scanners_cfg = settings.config.get("scanners", {})
    cheap_names = _enabled_cheap(scanners_cfg)
    wants_codeql = bool(scanners_cfg.get("codeql", True))
    seed_scanner_jobs(db, include_codeql=wants_codeql)
    codeql_max = int(settings.config.get("scan", {}).get("codeql_max_per_run", 5) or 5)
    codeql_done = 0

    def remaining_limit() -> int:
        if settings.limits.max_cases:
            return max(settings.limits.max_cases - touched, 0)
        return 1_000_000

    def time_left() -> bool:
        return not settings.limits.max_seconds or (time.time() - start < settings.limits.max_seconds)

    while remaining_limit() > 0 and time_left():
        progress = False

        # Always drain cheap pending work first. This is the important part for continuous runs:
        # new cases get cheap triage before more CodeQL begins.
        cheap_filter = _missing_any_runs_condition(cheap_names)
        cheap_cases = _query_cases(db, settings, cheap_filter, min(remaining_limit(), 50)) if cheap_filter else []
        if cheap_cases:
            cheap_cfg = _stage_config(settings.config, codeql=False, cheap=True)
            for case in cheap_cases:
                if remaining_limit() <= 0 or not time_left():
                    break
                try:
                    _run_case(db, case, cheap_cfg, "Cheap-scanning")
                    touched += 1
                    progress = True
                except Exception as e:
                    log.exception("Cheap scan failed for case %s", case["case_id"])
                    db.execute(
                        "UPDATE cases SET status='error', review_notes=COALESCE(review_notes,'') || ? WHERE id=?",
                        (f"\nCheap scan error: {e}", case["case_id"]),
                    )
            continue

        if not wants_codeql:
            break

        if codeql_done >= codeql_max:
            log.info("CodeQL per-run limit reached. codeql_done=%s limit=%s", codeql_done, codeql_max)
            break

        # Only run CodeQL once cheap scanners are complete for that case.
        codeql_filter = _has_all_runs_condition(cheap_names) + "\n" + _missing_codeql_condition()
        codeql_cases = _query_cases(db, settings, codeql_filter, 1)
        if codeql_cases:
            codeql_cfg = _stage_config(settings.config, codeql=True, cheap=False)
            case = codeql_cases[0]
            try:
                _run_case(db, case, codeql_cfg, "CodeQL-scanning")
                touched += 1
                codeql_done += 1
                progress = True
            except Exception as e:
                log.exception("CodeQL scan failed for case %s", case["case_id"])
                db.execute(
                    "UPDATE cases SET status='error', review_notes=COALESCE(review_notes,'') || ? WHERE id=?",
                    (f"\nCodeQL scan error: {e}", case["case_id"]),
                )
            continue

        if not progress:
            break

    update_case_stages(db)
    log.info("Scan complete. touched=%s codeql=%s", touched, codeql_done)
