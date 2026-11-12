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
    "schema_version": 1,
    "master_enabled": True,
    "pools": {
        "codeql_security": {
            "enabled": True,
            "priority": 100,
            "max_workers": 8,
            "partition_preferences": [
                "biggpu",
                "bigbatch",
            ],
        },
        "cheap_analysis": {
            "enabled": True,
            "priority": 50,
            "max_workers": 6,
            "partition_preferences": [
                "bigbatch",
                "biggpu",
            ],
        },
        "mining": {
            "enabled": True,
            "priority": 30,
            "max_workers": 4,
            "partition_preferences": [
                "stampede",
                "bigbatch",
                "batch",
                "biggpu",
            ],
        },
    },
    "updated_at": 0.0,
}


def policy_path(spool_root: str | Path) -> Path:
    return (
        Path(spool_root)
        / "control"
        / "pools.json"
    )


def normalize_policy(
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    source = payload if isinstance(payload, dict) else {}
    normalized = copy.deepcopy(DEFAULT_POLICY)

    normalized["master_enabled"] = bool(
        source.get(
            "master_enabled",
            normalized["master_enabled"],
        )
    )

    source_pools = source.get("pools")

    if not isinstance(source_pools, dict):
        source_pools = {}

    for pool in POOL_NAMES:
        source_pool = source_pools.get(pool)

        if not isinstance(source_pool, dict):
            source_pool = {}

        target = normalized["pools"][pool]

        target["enabled"] = bool(
            source_pool.get(
                "enabled",
                target["enabled"],
            )
        )

        try:
            target["priority"] = max(
                1,
                int(
                    source_pool.get(
                        "priority",
                        target["priority"],
                    )
                ),
            )
        except (TypeError, ValueError):
            pass

        try:
            target["max_workers"] = max(
                0,
                min(
                    32,
                    int(
                        source_pool.get(
                            "max_workers",
                            target["max_workers"],
                        )
                    ),
                ),
            )
        except (TypeError, ValueError):
            pass

        preferences = source_pool.get(
            "partition_preferences"
        )

        if isinstance(preferences, list):
            cleaned: list[str] = []

            for value in preferences:
                partition = str(value)

                if (
                    partition in PARTITION_LIMITS
                    and partition not in cleaned
                ):
                    cleaned.append(partition)

            if cleaned:
                target["partition_preferences"] = cleaned

    try:
        normalized["updated_at"] = float(
            source.get("updated_at") or time.time()
        )
    except (TypeError, ValueError):
        normalized["updated_at"] = time.time()

    return normalized


def save_pool_policy(
    spool_root: str | Path,
    policy: dict[str, Any],
) -> dict[str, Any]:
    normalized = normalize_policy(policy)
    normalized["updated_at"] = time.time()

    destination = policy_path(spool_root)
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
    path = policy_path(spool_root)

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
    pools = policy.get("pools")

    if not isinstance(pools, dict):
        return False

    pool_policy = pools.get(pool)

    if not isinstance(pool_policy, dict):
        return False

    return bool(
        policy.get("master_enabled", True)
    ) and bool(
        pool_policy.get("enabled", True)
    )
