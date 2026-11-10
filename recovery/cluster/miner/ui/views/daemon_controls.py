from __future__ import annotations

from typing import Any

import streamlit as st

from src.workers.daemon_controller import (
    ensure_active,
    reconcile,
    request_stop,
)


CONTROLS = (
    (
        "mining",
        "Continuous Mining",
        "Continuously discovers new qualifying GitHub cases.",
    ),
    (
        "cheap_analysis",
        "Cheap Static Analysis",
        "Semgrep, Gitleaks, dependency diff, OSV and Trivy.",
    ),
    (
        "codeql_security",
        "Security CodeQL",
        "Security-only CodeQL analysis on supported source files.",
    ),
)


def _status(row: dict[str, Any]) -> None:
    desired = bool(row.get("desired_enabled"))
    active = bool(row.get("cluster_active"))

    scheduler = str(
        row.get("scheduler_state_live")
        or row.get("scheduler_state")
        or "NOT_IN_QUEUE"
    )

    partition = str(row.get("partition") or "unknown")

    if desired and active:
        st.success(f"ON · {scheduler} · {partition}")
    elif active:
        st.warning(f"Stopping · {scheduler} · {partition}")
    elif desired:
        st.warning(f"Recovering allocation · {partition}")
    else:
        st.info("OFF · no active cluster allocation")

    current = str(row.get("current_unit") or "").strip()
    detail = str(row.get("detail") or "").strip()

    if current:
        st.caption(current)
    elif detail:
        st.caption(detail)

    job_id = row.get("slurm_job_id")
    heartbeat = row.get("heartbeat_at")

    metadata = []

    if job_id:
        metadata.append(f"Job {job_id}")

    if heartbeat:
        metadata.append(f"Heartbeat {heartbeat}")

    if metadata:
        st.caption(" · ".join(metadata))

    error = str(row.get("last_error") or "").strip()

    if error:
        st.error(error)


def render_daemon_controls(_settings: Any) -> None:
    st.subheader("Cluster controls")

    columns = st.columns(3)

    for column, control in zip(columns, CONTROLS):
        daemon_name, label, description = control

        with column:
            try:
                row = reconcile(daemon_name)
            except Exception as exc:
                st.error(f"{label}: {exc}")
                continue

            desired = bool(row.get("desired_enabled"))
            generation = int(row.get("generation") or 0)
            job_id = str(row.get("slurm_job_id") or "none")

            requested = st.toggle(
                label,
                value=desired,
                help=description,
                key=(
                    f"daemon-{daemon_name}-"
                    f"{int(desired)}-{generation}-{job_id}"
                ),
            )

            if requested != desired:
                try:
                    if requested:
                        ensure_active(daemon_name)
                    else:
                        request_stop(daemon_name)
                except Exception as exc:
                    st.error(str(exc))

                st.rerun()

            _status(row)

    st.divider()
