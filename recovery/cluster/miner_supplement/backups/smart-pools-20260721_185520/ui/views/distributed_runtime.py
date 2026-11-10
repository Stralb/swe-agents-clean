from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
POOLS = (
    ("mining", "Mining pool"),
    ("cheap_analysis", "Cheap pool"),
    ("codeql_security", "CodeQL pool"),
)
QUEUES = ("pending", "claimed", "results", "failed", "heartbeats")


def _spool_root() -> Path:
    return Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(ROOT / "data/distributed_spool"),
        )
    )


def _count(pool: str, queue: str) -> int:
    path = _spool_root() / pool / queue
    if not path.exists():
        return 0
    return sum(1 for _ in path.glob("*.json"))


def _json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _age_label(timestamp: float | int | None) -> str:
    if not timestamp:
        return "unknown"
    seconds = max(0, int(time.time() - float(timestamp)))
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h"


def _heartbeats(pool: str) -> list[dict[str, Any]]:
    directory = _spool_root() / pool / "heartbeats"
    rows: list[dict[str, Any]] = []
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("*.json")):
        row = _json(path)
        if not row:
            continue
        row["age"] = _age_label(row.get("updated_at") or path.stat().st_mtime)
        rows.append(row)
    return rows


def _status(name: str) -> dict[str, Any]:
    return _json(_spool_root() / "status" / f"{name}.json")


def render_distributed_runtime(_settings: Any, compact: bool = False) -> None:
    if compact:
        st.subheader("Distributed runtime")
    else:
        st.header("Distributed runtime")

    autoscaler = _status("autoscaler")
    coordinator = _status("coordinator")
    pool_status = autoscaler.get("pools", {}) if isinstance(autoscaler, dict) else {}

    columns = st.columns(3)
    for column, (pool, label) in zip(columns, POOLS):
        counts = {queue: _count(pool, queue) for queue in QUEUES}
        worker_rows = _heartbeats(pool)
        active_workers = sum(
            1
            for row in worker_rows
            if str(row.get("state") or "").lower() in {"working", "idle"}
            and time.time() - float(row.get("updated_at") or 0) <= 180
        )
        auto = pool_status.get(pool, {}) if isinstance(pool_status, dict) else {}

        with column:
            with st.container(border=True):
                st.markdown(f"### {label}")
                c1, c2 = st.columns(2)
                c1.metric("Pending", counts["pending"])
                c2.metric("Claimed", counts["claimed"])
                c3, c4 = st.columns(2)
                c3.metric("Awaiting import", counts["results"])
                c4.metric("Failed", counts["failed"])
                c5, c6 = st.columns(2)
                c5.metric("Workers", active_workers)
                c6.metric("Desired", auto.get("desired_workers", "—"))
                st.caption(
                    "Autoscaler: "
                    + str(auto.get("decision") or "unavailable")
                )

    if compact:
        return

    st.markdown("### Coordinator")
    if coordinator:
        st.json(coordinator)
    else:
        st.info("Coordinator status file is not available yet.")

    st.markdown("### Autoscaler")
    if autoscaler:
        st.json(autoscaler)
    else:
        st.info("Autoscaler status file is not available yet.")

    rows: list[dict[str, Any]] = []
    for pool, label in POOLS:
        for heartbeat in _heartbeats(pool):
            rows.append(
                {
                    "pool": label,
                    "worker_id": heartbeat.get("worker_id"),
                    "state": heartbeat.get("state"),
                    "task_id": heartbeat.get("task_id"),
                    "host": heartbeat.get("hostname"),
                    "slurm_job_id": heartbeat.get("slurm_job_id"),
                    "age": heartbeat.get("age"),
                    "detail": heartbeat.get("detail"),
                }
            )

    st.markdown("### Worker heartbeats")
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    else:
        st.info("No distributed worker heartbeats found.")
