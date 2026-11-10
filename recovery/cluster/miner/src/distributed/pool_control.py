from __future__ import annotations

import copy
import time
from pathlib import Path
from typing import Any

from src.distributed.spool import (
    atomic_replace_json,
    read_json,
)

POOL_NAMES = (
    "codeql_security",
    "cheap_analysis",
    "mining",
)

PARTITION_LIMITS = {
    "biggpu": 1,
    "bigbatch": 6,
    "stampede": 2,
    "batch": 13,
}

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": 2,
    "master_enabled": True,
    "scheduling_mode": "automatic",
    "max_total_workers": 7,
    "pools": {
        "codeql_security": {
            "enabled": True,
            "priority": 100,
            "max_workers": 7,
            "manual_workers": 5,
            "partition_preferences": [
                "biggpu",
                "bigbatch",
            ],
        },
        "cheap_analysis": {
            "enabled": True,
            "priority": 50,
            "max_workers": 3,
            "manual_workers": 1,
            "steady_workers": 1,
            "scale_up_workers": 2,
            "emergency_workers": 3,
            "scale_down_below": 30,
            "scale_up_at": 100,
            "emergency_at": 250,
            "partition_preferences": [
                "bigbatch",
                "batch",
            ],
        },
        "mining": {
            "enabled": True,
            "priority": 30,
            "max_workers": 1,
            "manual_workers": 1,
            "continuous_workers": 1,
            "partition_preferences": [
                "bigbatch",
                "batch",
            ],
        },
    },
    "updated_at": 0.0,
}


def _bounded_int(
    value: Any,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)

    return max(
        minimum,
        min(
            maximum,
            parsed,
        ),
    )


def policy_path(
    spool_root: str | Path,
) -> Path:
    return (
        Path(spool_root)
        / "control"
        / "pools.json"
    )


def normalize_policy(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    source = (
        payload
        if isinstance(payload, dict)
        else {}
    )

    normalized = copy.deepcopy(
        DEFAULT_POLICY
    )

    normalized["schema_version"] = 2

    normalized["master_enabled"] = bool(
        source.get(
            "master_enabled",
            normalized["master_enabled"],
        )
    )

    mode = str(
        source.get(
            "scheduling_mode",
            normalized["scheduling_mode"],
        )
    ).lower()

    normalized["scheduling_mode"] = (
        mode
        if mode in {
            "automatic",
            "manual",
        }
        else "automatic"
    )

    normalized["max_total_workers"] = (
        _bounded_int(
            source.get(
                "max_total_workers",
                normalized[
                    "max_total_workers"
                ],
            ),
            normalized[
                "max_total_workers"
            ],
            0,
            32,
        )
    )

    source_pools = source.get(
        "pools"
    )

    if not isinstance(
        source_pools,
        dict,
    ):
        source_pools = {}

    for pool in POOL_NAMES:
        source_pool = source_pools.get(
            pool
        )

        if not isinstance(
            source_pool,
            dict,
        ):
            source_pool = {}

        target = normalized[
            "pools"
        ][pool]

        target["enabled"] = bool(
            source_pool.get(
                "enabled",
                target["enabled"],
            )
        )

        target["priority"] = _bounded_int(
            source_pool.get(
                "priority",
                target["priority"],
            ),
            target["priority"],
            1,
            1000,
        )

        target["max_workers"] = _bounded_int(
            source_pool.get(
                "max_workers",
                target["max_workers"],
            ),
            target["max_workers"],
            0,
            32,
        )

        target["manual_workers"] = (
            _bounded_int(
                source_pool.get(
                    "manual_workers",
                    target[
                        "manual_workers"
                    ],
                ),
                target[
                    "manual_workers"
                ],
                0,
                target["max_workers"],
            )
        )

        for key in (
            "continuous_workers",
            "steady_workers",
            "scale_up_workers",
            "emergency_workers",
        ):
            if key not in target:
                continue

            target[key] = _bounded_int(
                source_pool.get(
                    key,
                    target[key],
                ),
                target[key],
                0,
                target["max_workers"],
            )

        for key in (
            "scale_down_below",
            "scale_up_at",
            "emergency_at",
        ):
            if key not in target:
                continue

            target[key] = _bounded_int(
                source_pool.get(
                    key,
                    target[key],
                ),
                target[key],
                0,
                1000000,
            )

        if pool == "cheap_analysis":
            target["scale_up_at"] = max(
                target["scale_down_below"] + 1,
                target["scale_up_at"],
            )

            target["emergency_at"] = max(
                target["scale_up_at"] + 1,
                target["emergency_at"],
            )

            target["scale_up_workers"] = max(
                target["steady_workers"],
                target["scale_up_workers"],
            )

            target["emergency_workers"] = max(
                target["scale_up_workers"],
                target["emergency_workers"],
            )

        preferences = source_pool.get(
            "partition_preferences"
        )

        if isinstance(
            preferences,
            list,
        ):
            cleaned: list[str] = []

            for value in preferences:
                partition = str(value)

                if (
                    partition in PARTITION_LIMITS
                    and partition not in cleaned
                ):
                    cleaned.append(
                        partition
                    )

            if cleaned:
                target[
                    "partition_preferences"
                ] = cleaned

    try:
        normalized["updated_at"] = float(
            source.get(
                "updated_at"
            )
            or time.time()
        )
    except (TypeError, ValueError):
        normalized["updated_at"] = (
            time.time()
        )

    return normalized


def save_pool_policy(
    spool_root: str | Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_policy(
        policy
    )

    normalized["updated_at"] = (
        time.time()
    )

    destination = policy_path(
        spool_root
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    atomic_replace_json(
        destination,
        normalized,
    )

    return normalized


def load_pool_policy(
    spool_root: str | Path,
) -> dict[str, Any]:
    path = policy_path(
        spool_root
    )

    if not path.exists():
        return save_pool_policy(
            spool_root,
            DEFAULT_POLICY,
        )

    try:
        return normalize_policy(
            read_json(path)
        )
    except Exception:
        return save_pool_policy(
            spool_root,
            DEFAULT_POLICY,
        )


def pool_enabled(
    policy: dict[str, Any],
    pool: str,
) -> bool:
    pools = policy.get(
        "pools"
    )

    if not isinstance(
        pools,
        dict,
    ):
        return False

    pool_policy = pools.get(
        pool
    )

    if not isinstance(
        pool_policy,
        dict,
    ):
        return False

    return bool(
        policy.get(
            "master_enabled",
            True,
        )
    ) and bool(
        pool_policy.get(
            "enabled",
            True,
        )
    )
