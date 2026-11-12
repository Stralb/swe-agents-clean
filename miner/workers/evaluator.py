from __future__ import annotations

import logging
import time
import uuid
from typing import Iterable

from miner.db.database import Database
from miner.settings import Settings
from miner.workers.job_queue import claim_job, heartbeat, reset_stale_jobs, run_scanner_job, seed_scanner_jobs, update_case_stages

log = logging.getLogger(__name__)

JOB_GROUPS = {
    "source": ["codeql"],
    "dependency": ["dependency_downgrade", "osv_dependency", "trivy_dependency"],
    "dependency-downgrade": ["dependency_downgrade"],
    "osv": ["osv_dependency"],
    "trivy": ["trivy_dependency"],
    "secret": ["secret_ci"],
    "codeql": ["codeql"],
    "cheap": ["semgrep_source", "secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency"],
    "all": ["secret_ci", "dependency_downgrade", "osv_dependency", "trivy_dependency", "codeql"],
}


def evaluate_loop(
    settings: Settings,
    *,
    job_group: str = "all",
    worker_id: str | None = None,
    max_loops: int | None = None,
    idle_seconds: int | None = None,
    exit_when_idle: bool = False,
    mode_label: str = "evaluate",
) -> int:
    db = Database(settings.db_path)
    worker_id = worker_id or f"eval-{job_group}-{uuid.uuid4().hex[:6]}"
    workers_cfg = settings.config.get("workers", {})
    max_loops = int(max_loops if max_loops is not None else workers_cfg.get("max_loops", 0) or 0)
    idle_seconds = int(idle_seconds if idle_seconds is not None else workers_cfg.get("idle_seconds", 10) or 10)
    job_types = JOB_GROUPS.get(job_group, [job_group])
    reset_stale_jobs(
        db,
        stale_minutes=int(workers_cfg.get("job_stale_minutes", 60) or 60),
        codeql_stale_minutes=int(workers_cfg.get("codeql_stale_minutes", 180) or 180),
    )
    include_codeql = "codeql" in job_types
    processed = 0
    loops = 0
    while True:
        loops += 1
        seed_scanner_jobs(db, include_codeql=include_codeql)
        heartbeat(db, worker_id, f"evaluator:{job_group}", mode_label, "claiming", ",".join(job_types))
        job = claim_job(db, job_types, worker_id=worker_id)
        if job is None:
            update_case_stages(db)
            if exit_when_idle:
                heartbeat(db, worker_id, f"evaluator:{job_group}", mode_label, "idle", "no pending jobs; exiting")
                break
            heartbeat(db, worker_id, f"evaluator:{job_group}", mode_label, "idle", f"polling again in {idle_seconds}s")
            if max_loops and loops >= max_loops:
                break
            time.sleep(idle_seconds)
            continue
        heartbeat(db, worker_id, f"evaluator:{job_group}", mode_label, "running", f"case={job.case_id} job={job.job_type}")
        run_scanner_job(db, settings, job)
        processed += 1
        heartbeat(db, worker_id, f"evaluator:{job_group}", mode_label, "done", f"processed={processed}")
        if max_loops and loops >= max_loops:
            break
    return processed
