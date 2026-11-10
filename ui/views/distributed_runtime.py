from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.distributed.pool_control import (
    PARTITION_LIMITS,
    load_pool_policy,
    save_pool_policy,
)

ROOT = Path(__file__).resolve().parents[2]

POOLS = (
    (
        "codeql_security",
        "CodeQL pool",
    ),
    (
        "cheap_analysis",
        "Cheap-analysis pool",
    ),
    (
        "mining",
        "Mining pool",
    ),
)

QUEUES = (
    "pending",
    "claimed",
    "results",
    "failed",
    "heartbeats",
)


def _spool_root() -> Path:
    return Path(
        os.getenv(
            "DISTRIBUTED_SPOOL_ROOT",
            str(
                ROOT
                / "data"
                / "distributed_spool"
            ),
        )
    )


def _count(
    pool: str,
    queue: str,
) -> int:
    path = (
        _spool_root()
        / pool
        / queue
    )

    if not path.exists():
        return 0

    return sum(
        1
        for _ in path.glob("*.json")
    )


def _json(
    path: Path,
) -> dict[str, Any]:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}


def _age_label(
    timestamp: float | int | None,
) -> str:
    if not timestamp:
        return "unknown"

    seconds = max(
        0,
        int(
            time.time()
            - float(timestamp)
        ),
    )

    if seconds < 60:
        return f"{seconds}s"

    if seconds < 3600:
        return f"{seconds // 60}m"

    return f"{seconds // 3600}h"


def _heartbeats(
    pool: str,
) -> list[dict[str, Any]]:
    directory = (
        _spool_root()
        / pool
        / "heartbeats"
    )

    rows: list[dict[str, Any]] = []

    if not directory.exists():
        return rows

    for path in sorted(
        directory.glob("*.json")
    ):
        row = _json(path)

        if not row:
            continue

        row["age"] = _age_label(
            row.get("updated_at")
            or path.stat().st_mtime
        )

        rows.append(row)

    return rows


def _status(
    name: str,
) -> dict[str, Any]:
    return _json(
        _spool_root()
        / "status"
        / f"{name}.json"
    )


def _apply_all(
    enabled: bool,
) -> None:
    policy = load_pool_policy(
        _spool_root()
    )

    updated = copy.deepcopy(
        policy
    )

    updated["master_enabled"] = enabled

    for pool, _ in POOLS:
        updated["pools"][pool][
            "enabled"
        ] = enabled

    save_pool_policy(
        _spool_root(),
        updated,
    )

    st.rerun()


def _render_controls(
    policy: dict[str, Any],
) -> None:
    st.markdown(
        "### Pool controls"
    )

    st.caption(
        "Turning the master switch off cancels every "
        "worker-pool Slurm job. The coordinator, "
        "autoscaler and dashboard remain online so the "
        "system can be switched on again."
    )

    action_columns = st.columns(2)

    if action_columns[0].button(
        "Enable all pools",
        width="stretch",
    ):
        _apply_all(True)

    if action_columns[1].button(
        "Stop all worker pools",
        width="stretch",
        type="primary",
    ):
        _apply_all(False)

    version = int(
        float(
            policy.get("updated_at")
            or 0
        )
    )

    with st.form(
        f"pool-controls-{version}"
    ):
        master_enabled = st.toggle(
            "Worker pools enabled",
            value=bool(
                policy.get(
                    "master_enabled",
                    True,
                )
            ),
        )

        columns = st.columns(3)
        values: dict[
            str,
            dict[str, Any],
        ] = {}

        for column, (
            pool,
            label,
        ) in zip(
            columns,
            POOLS,
        ):
            current = policy[
                "pools"
            ][pool]

            with column:
                with st.container(
                    border=True
                ):
                    st.markdown(
                        f"**{label}**"
                    )

                    enabled = st.toggle(
                        "Enabled",
                        value=bool(
                            current[
                                "enabled"
                            ]
                        ),
                        key=(
                            f"enabled-"
                            f"{pool}-"
                            f"{version}"
                        ),
                    )

                    maximum = st.number_input(
                        "Maximum workers",
                        min_value=0,
                        max_value=32,
                        value=int(
                            current[
                                "max_workers"
                            ]
                        ),
                        step=1,
                        key=(
                            f"maximum-"
                            f"{pool}-"
                            f"{version}"
                        ),
                    )

                    st.caption(
                        " → ".join(
                            current[
                                "partition_preferences"
                            ]
                        )
                    )

                    values[pool] = {
                        "enabled": enabled,
                        "max_workers": int(
                            maximum
                        ),
                    }

        submitted = st.form_submit_button(
            "Apply pool controls",
            type="primary",
            width="stretch",
        )

    if submitted:
        updated = copy.deepcopy(
            policy
        )

        updated[
            "master_enabled"
        ] = master_enabled

        for pool, values_for_pool in (
            values.items()
        ):
            updated["pools"][pool][
                "enabled"
            ] = values_for_pool[
                "enabled"
            ]

            updated["pools"][pool][
                "max_workers"
            ] = values_for_pool[
                "max_workers"
            ]

        save_pool_policy(
            _spool_root(),
            updated,
        )

        st.success(
            "Pool policy saved. The autoscaler "
            "will apply it on its next cycle."
        )

        time.sleep(0.3)
        st.rerun()

    st.caption(
        "Concurrent-job limits observed from Slurm: "
        + ", ".join(
            f"{partition}={limit}"
            for partition, limit
            in PARTITION_LIMITS.items()
        )
    )


def render_distributed_runtime(
    _settings: Any,
    compact: bool = False,
) -> None:
    if compact:
        st.subheader(
            "Distributed runtime"
        )
    else:
        st.header(
            "Distributed runtime"
        )

    policy = load_pool_policy(
        _spool_root()
    )

    if not compact:
        _render_controls(policy)

    autoscaler = _status(
        "autoscaler"
    )

    coordinator = _status(
        "coordinator"
    )

    pool_status = (
        autoscaler.get(
            "pools",
            {},
        )
        if isinstance(
            autoscaler,
            dict,
        )
        else {}
    )

    columns = st.columns(3)

    for column, (
        pool,
        label,
    ) in zip(
        columns,
        POOLS,
    ):
        counts = {
            queue: _count(
                pool,
                queue,
            )
            for queue in QUEUES
        }

        worker_rows = _heartbeats(
            pool
        )

        active_workers = sum(
            1
            for row in worker_rows
            if str(
                row.get("state")
                or ""
            ).lower()
            in {
                "working",
                "idle",
            }
            and time.time()
            - float(
                row.get(
                    "updated_at"
                )
                or 0
            )
            <= 180
        )

        auto = (
            pool_status.get(
                pool,
                {},
            )
            if isinstance(
                pool_status,
                dict,
            )
            else {}
        )

        enabled = bool(
            auto.get(
                "enabled",
                policy.get(
                    "master_enabled",
                    True,
                )
                and policy[
                    "pools"
                ][pool]["enabled"],
            )
        )

        with column:
            with st.container(
                border=True
            ):
                st.markdown(
                    f"### {label}"
                )

                st.caption(
                    "Enabled"
                    if enabled
                    else "Paused"
                )

                c1, c2 = st.columns(2)
                c1.metric(
                    "Pending",
                    counts["pending"],
                )
                c2.metric(
                    "Claimed",
                    counts["claimed"],
                )

                c3, c4 = st.columns(2)
                c3.metric(
                    "Awaiting import",
                    counts["results"],
                )
                c4.metric(
                    "Failed",
                    counts["failed"],
                )

                c5, c6 = st.columns(2)
                c5.metric(
                    "Workers",
                    active_workers,
                )
                c6.metric(
                    "Desired",
                    auto.get(
                        "desired_workers",
                        "—",
                    ),
                )

                st.caption(
                    "Autoscaler: "
                    + str(
                        auto.get(
                            "decision"
                        )
                        or "unavailable"
                    )
                )

                preferences = auto.get(
                    "partition_preferences"
                ) or policy[
                    "pools"
                ][pool][
                    "partition_preferences"
                ]

                st.caption(
                    "Preferred: "
                    + " → ".join(
                        preferences
                    )
                )

    if compact:
        return

    partition_capacity = (
        autoscaler.get(
            "partition_capacity",
            {},
        )
        if isinstance(
            autoscaler,
            dict,
        )
        else {}
    )

    occupancy = (
        autoscaler.get(
            "partition_occupancy",
            {},
        )
        if isinstance(
            autoscaler,
            dict,
        )
        else {}
    )

    partition_rows = []

    for partition, limit in (
        PARTITION_LIMITS.items()
    ):
        capacity = (
            partition_capacity.get(
                partition,
                {},
            )
        )

        partition_rows.append(
            {
                "partition": partition,
                "job_limit": limit,
                "current_jobs": occupancy.get(
                    partition,
                    0,
                ),
                "idle_nodes": capacity.get(
                    "idle_nodes",
                    0,
                ),
                "usable_nodes": capacity.get(
                    "usable_nodes",
                    0,
                ),
            }
        )

    st.markdown(
        "### Partition allocation"
    )

    st.dataframe(
        pd.DataFrame(
            partition_rows
        ),
        hide_index=True,
        width="stretch",
    )

    job_rows: list[
        dict[str, Any]
    ] = []

    for pool, label in POOLS:
        auto = pool_status.get(
            pool,
            {},
        )

        for job in auto.get(
            "jobs",
            [],
        ):
            job_rows.append(
                {
                    "pool": label,
                    "job_id": job.get(
                        "job_id"
                    ),
                    "partition": job.get(
                        "partition"
                    ),
                    "state": job.get(
                        "state"
                    ),
                    "name": job.get(
                        "name"
                    ),
                }
            )

    st.markdown(
        "### Managed Slurm jobs"
    )

    if job_rows:
        st.dataframe(
            pd.DataFrame(
                job_rows
            ),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "No managed worker jobs are active."
        )

    st.markdown(
        "### Coordinator"
    )

    if coordinator:
        st.json(coordinator)
    else:
        st.info(
            "Coordinator status file is not available yet."
        )

    st.markdown(
        "### Autoscaler"
    )

    if autoscaler:
        st.json(autoscaler)
    else:
        st.info(
            "Autoscaler status file is not available yet."
        )

    rows: list[
        dict[str, Any]
    ] = []

    for pool, label in POOLS:
        for heartbeat in _heartbeats(
            pool
        ):
            rows.append(
                {
                    "pool": label,
                    "worker_id": heartbeat.get(
                        "worker_id"
                    ),
                    "state": heartbeat.get(
                        "state"
                    ),
                    "task_id": heartbeat.get(
                        "task_id"
                    ),
                    "partition": heartbeat.get(
                        "partition"
                    ),
                    "host": heartbeat.get(
                        "hostname"
                    ),
                    "slurm_job_id": heartbeat.get(
                        "slurm_job_id"
                    ),
                    "age": heartbeat.get(
                        "age"
                    ),
                    "detail": heartbeat.get(
                        "detail"
                    ),
                }
            )

    st.markdown(
        "### Worker heartbeats"
    )

    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            width="stretch",
        )
    else:
        st.info(
            "No distributed worker heartbeats found."
        )
