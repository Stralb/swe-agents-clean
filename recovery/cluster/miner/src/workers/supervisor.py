from __future__ import annotations

import argparse
import logging
import threading
import time
import uuid
from typing import Callable

from src.db.database import Database
from src.pipeline.collect_pipeline import collect
from src.settings import Settings, load_settings
from src.utils.logging import setup_logging
from src.workers.evaluator import evaluate_loop
from src.workers.job_queue import heartbeat, reset_running_jobs_on_start, seed_scanner_jobs, update_case_stages

log = logging.getLogger(__name__)


def _run_collect_once(settings: Settings, worker_id: str) -> None:
    db = Database(settings.db_path)
    heartbeat(db, worker_id, "github", "mine", "running", "collecting GitHub candidates")
    try:
        collect(settings)
        created = seed_scanner_jobs(db, include_codeql=True)
        heartbeat(db, worker_id, "github", "mine", "idle", f"collection pass complete; seeded_jobs={created}")
    except KeyboardInterrupt:
        heartbeat(db, worker_id, "github", "mine", "stopped", "interrupted")
        raise
    except Exception as exc:
        log.exception("GitHub mining pass failed")
        heartbeat(db, worker_id, "github", "mine", "error", str(exc))
        db.execute("INSERT INTO pipeline_events(event_type, detail) VALUES ('github_error', ?)", (str(exc)[:1000],))


def mine_loop(settings: Settings, *, max_loops: int = 0, idle_seconds: int = 30, worker_id: str | None = None) -> None:
    worker_id = worker_id or f"github-{uuid.uuid4().hex[:6]}"
    loops = 0
    while True:
        loops += 1
        _run_collect_once(settings, worker_id)
        if max_loops and loops >= max_loops:
            break
        time.sleep(idle_seconds)


def _start_thread(name: str, target: Callable[[], None]) -> threading.Thread:
    t = threading.Thread(name=name, target=target, daemon=True)
    t.start()
    return t


def run_supervisor(settings: Settings, *, mode: str, github_workers: int, source_workers: int, dependency_workers: int, secret_workers: int, codeql_workers: int, max_loops: int = 0, idle_seconds: int | None = None, exit_when_drained: bool = False) -> None:
    db = Database(settings.db_path)
    if mode == "live" and max_loops:
        # Live mode is the production continuous pipeline. It must keep mining and
        # evaluator workers polling for future jobs. A bounded --max-loops value is
        # safe for mine/evaluate smoke tests, but it caused live evaluators to exit
        # before GitHub mining produced scanner jobs. Ignore it in live mode.
        db.execute(
            "INSERT INTO pipeline_events(event_type, detail) VALUES ('live_max_loops_ignored', ?)",
            (f"Ignored --max-loops={max_loops} in live mode so workers keep polling.",),
        )
        log.warning("Ignoring --max-loops=%s in live mode; live workers must poll continuously", max_loops)
        max_loops = 0
    if mode in {"evaluate", "evaluate-cheap", "evaluate-codeql"}:
        reset_running_jobs_on_start(db, reason="Reset running job on evaluate-only startup.")
    seed_scanner_jobs(db, include_codeql=codeql_workers > 0)
    update_case_stages(db)
    idle = int(idle_seconds if idle_seconds is not None else settings.config.get("workers", {}).get("idle_seconds", 10) or 10)
    threads: list[threading.Thread] = []

    if mode in {"live", "mine"}:
        for i in range(max(0, github_workers)):
            threads.append(_start_thread(f"github-{i}", lambda i=i: mine_loop(settings, max_loops=max_loops, idle_seconds=idle, worker_id=f"github-{i}")))

    if mode in {"live", "evaluate", "evaluate-cheap", "evaluate-codeql"}:
        if mode == "evaluate-cheap":
            source_workers = source_workers or 1
            dependency_workers = dependency_workers or 1
            secret_workers = secret_workers or 1
            codeql_workers = 0
        if mode == "evaluate-codeql":
            source_workers = dependency_workers = secret_workers = 0
            codeql_workers = codeql_workers or 1
        for i in range(max(0, source_workers)):
            threads.append(_start_thread(f"source-{i}", lambda i=i: evaluate_loop(settings, job_group="source", worker_id=f"source-{i}", max_loops=max_loops, idle_seconds=idle, exit_when_idle=exit_when_drained, mode_label=mode)))
        for i in range(max(0, dependency_workers)):
            threads.append(_start_thread(f"dependency-{i}", lambda i=i: evaluate_loop(settings, job_group="dependency", worker_id=f"dependency-{i}", max_loops=max_loops, idle_seconds=idle, exit_when_idle=exit_when_drained, mode_label=mode)))
        for i in range(max(0, secret_workers)):
            threads.append(_start_thread(f"secret-{i}", lambda i=i: evaluate_loop(settings, job_group="secret", worker_id=f"secret-{i}", max_loops=max_loops, idle_seconds=idle, exit_when_idle=exit_when_drained, mode_label=mode)))
        for i in range(max(0, codeql_workers)):
            threads.append(_start_thread(f"codeql-{i}", lambda i=i: evaluate_loop(settings, job_group="codeql", worker_id=f"codeql-{i}", max_loops=max_loops, idle_seconds=idle, exit_when_idle=exit_when_drained, mode_label=mode)))

    if not threads:
        raise SystemExit(f"No workers enabled for mode={mode}")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        log.info("Supervisor stopped by user")
        db.execute("INSERT INTO pipeline_events(event_type, detail) VALUES ('supervisor_stopped', 'KeyboardInterrupt')")


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Continuous mining/evaluation worker supervisor")
    parser.add_argument("--mode", choices=["live", "mine", "evaluate", "evaluate-cheap", "evaluate-codeql"], default="live")
    parser.add_argument("--github-workers", type=int, default=1)
    parser.add_argument("--source-workers", type=int, default=1)
    parser.add_argument("--dependency-workers", type=int, default=1)
    parser.add_argument("--secret-workers", type=int, default=1)
    parser.add_argument("--codeql-workers", type=int, default=0)
    parser.add_argument("--max-loops", type=int, default=0, help="0 means indefinite until stopped")
    parser.add_argument("--idle-seconds", type=int, default=None)
    parser.add_argument("--exit-when-drained", action="store_true", help="For evaluate modes: exit once no pending jobs remain instead of sleeping forever")
    args = parser.parse_args()
    settings = load_settings()
    if args.mode == "mine":
        args.source_workers = args.dependency_workers = args.secret_workers = args.codeql_workers = 0
    if args.mode == "evaluate":
        args.github_workers = 0
    run_supervisor(
        settings,
        mode=args.mode,
        github_workers=args.github_workers,
        source_workers=args.source_workers,
        dependency_workers=args.dependency_workers,
        secret_workers=args.secret_workers,
        codeql_workers=args.codeql_workers,
        max_loops=args.max_loops,
        idle_seconds=args.idle_seconds,
        exit_when_drained=args.exit_when_drained,
    )


if __name__ == "__main__":
    main()
