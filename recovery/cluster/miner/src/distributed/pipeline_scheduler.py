from __future__ import annotations

from typing import Any

POOLS = (
    "codeql_security",
    "cheap_analysis",
    "mining",
)


def _enabled(
    policy: dict[str, Any],
    pool: str,
) -> bool:
    return bool(
        policy.get(
            "master_enabled",
            True,
        )
    ) and bool(
        policy.get(
            "pools",
            {},
        ).get(
            pool,
            {},
        ).get(
            "enabled",
            True,
        )
    )


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _backlog(
    counts: dict[str, dict[str, int]],
    pool: str,
) -> int:
    pool_counts = counts.get(
        pool,
        {},
    )

    return max(
        0,
        _integer(
            pool_counts.get(
                "pending"
            )
        )
        + _integer(
            pool_counts.get(
                "claimed"
            )
        ),
    )


def _previous_desired(
    previous_status: dict[str, Any],
    pool: str,
) -> int:
    return max(
        0,
        _integer(
            previous_status.get(
                "pools",
                {},
            ).get(
                pool,
                {},
            ).get(
                "desired_workers"
            )
        ),
    )


def _cap(
    policy: dict[str, Any],
    pool: str,
    requested: int,
) -> int:
    maximum = max(
        0,
        _integer(
            policy[
                "pools"
            ][pool].get(
                "max_workers"
            )
        ),
    )

    return max(
        0,
        min(
            maximum,
            int(requested),
        ),
    )


def _manual_targets(
    policy: dict[str, Any],
    budget: int,
) -> tuple[
    dict[str, int],
    dict[str, str],
]:
    requested = {
        pool: (
            _cap(
                policy,
                pool,
                policy[
                    "pools"
                ][pool].get(
                    "manual_workers",
                    0,
                ),
            )
            if _enabled(
                policy,
                pool,
            )
            else 0
        )
        for pool in POOLS
    }

    targets = {
        pool: 0
        for pool in POOLS
    }

    remaining = budget

    ordered = sorted(
        POOLS,
        key=lambda pool: _integer(
            policy[
                "pools"
            ][pool].get(
                "priority",
                1,
            )
        ),
        reverse=True,
    )

    for pool in ordered:
        granted = min(
            requested[pool],
            remaining,
        )

        targets[pool] = granted
        remaining -= granted

    reasons = {
        pool: (
            "manual request=%s; granted=%s"
            % (
                requested[pool],
                targets[pool],
            )
        )
        for pool in POOLS
    }

    return targets, reasons


def compute_targets(
    policy: dict[str, Any],
    counts: dict[
        str,
        dict[str, int],
    ],
    previous_status: (
        dict[str, Any] | None
    ) = None,
) -> tuple[
    dict[str, int],
    dict[str, str],
    dict[str, Any],
]:
    previous = (
        previous_status
        if isinstance(
            previous_status,
            dict,
        )
        else {}
    )

    budget = max(
        0,
        _integer(
            policy.get(
                "max_total_workers",
                7,
            ),
            7,
        ),
    )

    backlogs = {
        pool: _backlog(
            counts,
            pool,
        )
        for pool in POOLS
    }

    if not bool(
        policy.get(
            "master_enabled",
            True,
        )
    ):
        targets = {
            pool: 0
            for pool in POOLS
        }

        reasons = {
            pool: "master switch disabled"
            for pool in POOLS
        }

        allocation = {
            "mode": str(
                policy.get(
                    "scheduling_mode",
                    "automatic",
                )
            ),
            "worker_budget": budget,
            "backlogs": backlogs,
            "targets": targets,
            "allocated_workers": 0,
            "spare_workers": budget,
        }

        return (
            targets,
            reasons,
            allocation,
        )

    mode = str(
        policy.get(
            "scheduling_mode",
            "automatic",
        )
    ).lower()

    if mode == "manual":
        targets, reasons = (
            _manual_targets(
                policy,
                budget,
            )
        )

        allocated = sum(
            targets.values()
        )

        allocation = {
            "mode": "manual",
            "worker_budget": budget,
            "backlogs": backlogs,
            "targets": targets,
            "allocated_workers": (
                allocated
            ),
            "spare_workers": max(
                0,
                budget - allocated,
            ),
        }

        return (
            targets,
            reasons,
            allocation,
        )

    targets = {
        pool: 0
        for pool in POOLS
    }

    reasons = {
        pool: ""
        for pool in POOLS
    }

    mining_policy = policy[
        "pools"
    ]["mining"]

    mining_floor = (
        _cap(
            policy,
            "mining",
            mining_policy.get(
                "continuous_workers",
                1,
            ),
        )
        if _enabled(
            policy,
            "mining",
        )
        else 0
    )

    cheap_policy = policy[
        "pools"
    ]["cheap_analysis"]

    cheap_backlog = backlogs[
        "cheap_analysis"
    ]

    previous_cheap = (
        _previous_desired(
            previous,
            "cheap_analysis",
        )
    )

    cheap_target = 0
    cheap_band = "empty"

    if (
        _enabled(
            policy,
            "cheap_analysis",
        )
        and cheap_backlog > 0
    ):
        steady = _integer(
            cheap_policy.get(
                "steady_workers",
                1,
            ),
            1,
        )

        scale_up_workers = _integer(
            cheap_policy.get(
                "scale_up_workers",
                2,
            ),
            2,
        )

        emergency_workers = _integer(
            cheap_policy.get(
                "emergency_workers",
                3,
            ),
            3,
        )

        scale_down_below = _integer(
            cheap_policy.get(
                "scale_down_below",
                30,
            ),
            30,
        )

        scale_up_at = _integer(
            cheap_policy.get(
                "scale_up_at",
                100,
            ),
            100,
        )

        emergency_at = _integer(
            cheap_policy.get(
                "emergency_at",
                250,
            ),
            250,
        )

        if cheap_backlog >= emergency_at:
            cheap_target = (
                emergency_workers
            )

            cheap_band = "emergency"

        elif (
            previous_cheap
            >= emergency_workers
            and cheap_backlog
            >= scale_up_at
        ):
            cheap_target = (
                emergency_workers
            )

            cheap_band = (
                "emergency-hold"
            )

        elif cheap_backlog >= scale_up_at:
            cheap_target = (
                scale_up_workers
            )

            cheap_band = "high"

        elif (
            previous_cheap
            >= scale_up_workers
            and cheap_backlog
            >= scale_down_below
        ):
            cheap_target = (
                scale_up_workers
            )

            cheap_band = "high-hold"

        else:
            cheap_target = steady
            cheap_band = "steady"

        cheap_target = _cap(
            policy,
            "cheap_analysis",
            cheap_target,
        )

    codeql_backlog = backlogs[
        "codeql_security"
    ]

    codeql_floor = (
        1
        if (
            _enabled(
                policy,
                "codeql_security",
            )
            and codeql_backlog > 0
        )
        else 0
    )

    requested_floors = {
        "codeql_security": (
            codeql_floor
        ),
        "cheap_analysis": (
            cheap_target
        ),
        "mining": mining_floor,
    }

    remaining = budget

    # Preserve the downstream bottleneck first when the
    # configured budget becomes unusually small.
    for pool in (
        "codeql_security",
        "cheap_analysis",
        "mining",
    ):
        granted = min(
            requested_floors[pool],
            remaining,
        )

        targets[pool] = granted
        remaining -= granted

    # CodeQL receives all residual capacity because it is
    # normally the expensive downstream bottleneck.
    if (
        remaining > 0
        and codeql_backlog > 0
        and _enabled(
            policy,
            "codeql_security",
        )
    ):
        additional = min(
            remaining,
            max(
                0,
                _cap(
                    policy,
                    "codeql_security",
                    1000000,
                )
                - targets[
                    "codeql_security"
                ],
            ),
        )

        targets[
            "codeql_security"
        ] += additional

        remaining -= additional

    # When CodeQL is empty, spare workers may help the
    # cheap-analysis queue up to its configured maximum.
    if (
        remaining > 0
        and cheap_backlog > 0
        and _enabled(
            policy,
            "cheap_analysis",
        )
    ):
        additional = min(
            remaining,
            max(
                0,
                _cap(
                    policy,
                    "cheap_analysis",
                    1000000,
                )
                - targets[
                    "cheap_analysis"
                ],
            ),
        )

        targets[
            "cheap_analysis"
        ] += additional

        remaining -= additional

    reasons["mining"] = (
        "continuous producer floor=%s"
        % mining_floor
    )

    reasons["cheap_analysis"] = (
        "backlog=%s; band=%s; previous=%s"
        % (
            cheap_backlog,
            cheap_band,
            previous_cheap,
        )
    )

    reasons["codeql_security"] = (
        "backlog=%s; residual capacity after "
        "mining and cheap-analysis guarantees"
        % codeql_backlog
    )

    allocated = sum(
        targets.values()
    )

    allocation = {
        "mode": "automatic",
        "worker_budget": budget,
        "backlogs": backlogs,
        "previous_desired": {
            pool: _previous_desired(
                previous,
                pool,
            )
            for pool in POOLS
        },
        "requested_floors": (
            requested_floors
        ),
        "cheap_backlog_band": (
            cheap_band
        ),
        "targets": targets,
        "allocated_workers": allocated,
        "spare_workers": max(
            0,
            budget - allocated,
        ),
    }

    return (
        targets,
        reasons,
        allocation,
    )
