from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.db.database import Database


@dataclass(frozen=True)
class ExplorationDecision:
    batch_sequence: int
    exploration_share: float
    reason: str
    known_processed: int
    known_new_candidates: int
    known_duplicate_prs: int
    cooldown_repos: tuple[str, ...]


def ensure_schema(db: Database) -> None:
    """Create controller-only tables without changing the research schema."""

    statements = (
        """
        CREATE TABLE IF NOT EXISTS mining_controller_batches (
            batch_id TEXT PRIMARY KEY,
            batch_sequence INTEGER NOT NULL UNIQUE,
            exploration_share REAL NOT NULL,
            exploration_shards INTEGER NOT NULL,
            exploitation_shards INTEGER NOT NULL,
            known_processed INTEGER NOT NULL DEFAULT 0,
            known_new_candidates INTEGER NOT NULL DEFAULT 0,
            known_duplicate_prs INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS mining_repo_batch_outcomes (
            task_id TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            batch_sequence INTEGER NOT NULL,
            lane TEXT NOT NULL,
            repo_full_name TEXT NOT NULL,
            raw_records INTEGER NOT NULL DEFAULT 0,
            processed_records INTEGER NOT NULL DEFAULT 0,
            new_prs INTEGER NOT NULL DEFAULT 0,
            already_seen_prs INTEGER NOT NULL DEFAULT 0,
            new_unique_candidates INTEGER NOT NULL DEFAULT 0,
            duplicate_candidates INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(task_id, repo_full_name)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_mining_repo_outcomes_batch
        ON mining_repo_batch_outcomes(batch_sequence, lane)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_mining_repo_outcomes_repo
        ON mining_repo_batch_outcomes(repo_full_name, batch_sequence)
        """,
        """
        CREATE TABLE IF NOT EXISTS mining_repo_cooldowns (
            repo_full_name TEXT PRIMARY KEY,
            triggered_by_sequence INTEGER NOT NULL,
            until_sequence INTEGER NOT NULL,
            reason TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )

    for statement in statements:
        db.execute(statement)


def _float_setting(
    settings: dict[str, object],
    name: str,
    default: float,
) -> float:
    try:
        return float(settings.get(name, default))
    except (TypeError, ValueError):
        return default


def _int_setting(
    settings: dict[str, object],
    name: str,
    default: int,
) -> int:
    try:
        return int(settings.get(name, default))
    except (TypeError, ValueError):
        return default


def _recent_exploitation_batches(
    db: Database,
    count: int,
) -> list[dict[str, Any]]:
    return db.query(
        """
        SELECT
            batch_sequence,
            SUM(processed_records) AS processed,
            SUM(new_unique_candidates) AS new_candidates,
            SUM(already_seen_prs) AS duplicate_prs,
            SUM(new_prs) AS new_prs
        FROM mining_repo_batch_outcomes
        WHERE lane='exploit'
        GROUP BY batch_sequence
        ORDER BY batch_sequence DESC
        LIMIT ?
        """,
        (max(1, count),),
    )


def _refresh_cooldowns(
    db: Database,
    *,
    current_sequence: int,
    settings: dict[str, object],
) -> tuple[str, ...]:
    low_batches = max(
        1,
        _int_setting(settings, "low_yield_batches", 2),
    )
    minimum_records = max(
        1,
        _int_setting(settings, "saturation_min_records", 20),
    )
    maximum_candidates = max(
        0,
        _int_setting(settings, "saturation_max_new_candidates", 1),
    )
    duplicate_threshold = min(
        1.0,
        max(
            0.0,
            _float_setting(settings, "duplicate_threshold", 0.80),
        ),
    )
    cooldown_batches = max(
        1,
        _int_setting(settings, "cooldown_batches", 3),
    )

    rows = db.query(
        """
        SELECT
            repo_full_name,
            batch_sequence,
            SUM(processed_records) AS processed,
            SUM(new_prs) AS new_prs,
            SUM(already_seen_prs) AS already_seen_prs,
            SUM(new_unique_candidates) AS new_candidates
        FROM mining_repo_batch_outcomes
        WHERE lane='exploit'
        GROUP BY repo_full_name, batch_sequence
        ORDER BY repo_full_name, batch_sequence DESC
        """
    )

    by_repo: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        history = by_repo.setdefault(
            str(row["repo_full_name"]),
            [],
        )
        if len(history) < low_batches:
            history.append(row)

    existing = {
        str(row["repo_full_name"]): row
        for row in db.query(
            """
            SELECT repo_full_name, triggered_by_sequence, until_sequence
            FROM mining_repo_cooldowns
            """
        )
    }

    for repo_full_name, history in by_repo.items():
        if len(history) < low_batches:
            continue

        latest_sequence = int(history[0]["batch_sequence"] or 0)
        previous_trigger = int(
            existing.get(repo_full_name, {}).get(
                "triggered_by_sequence",
                0,
            )
            or 0
        )

        # Do not re-trigger from the same old observations after a cooldown
        # expires. The repository must be sampled again first.
        if latest_sequence <= previous_trigger:
            continue

        low_yield = all(
            int(row["processed"] or 0) >= minimum_records
            and int(row["new_candidates"] or 0) <= maximum_candidates
            for row in history
        )

        latest_prs = (
            int(history[0]["new_prs"] or 0)
            + int(history[0]["already_seen_prs"] or 0)
        )
        latest_duplicate_rate = (
            int(history[0]["already_seen_prs"] or 0)
            / latest_prs
            if latest_prs
            else 0.0
        )
        duplicate_saturated = (
            int(history[0]["processed"] or 0) >= minimum_records
            and latest_duplicate_rate >= duplicate_threshold
        )

        if not (low_yield or duplicate_saturated):
            continue

        reason = (
            "duplicate_saturation"
            if duplicate_saturated
            else "consecutive_low_yield"
        )
        db.execute(
            """
            INSERT INTO mining_repo_cooldowns(
                repo_full_name,
                triggered_by_sequence,
                until_sequence,
                reason,
                updated_at
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_full_name) DO UPDATE SET
                triggered_by_sequence=excluded.triggered_by_sequence,
                until_sequence=excluded.until_sequence,
                reason=excluded.reason,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                repo_full_name,
                latest_sequence,
                current_sequence + cooldown_batches - 1,
                reason,
            ),
        )

    return tuple(
        str(row["repo_full_name"])
        for row in db.query(
            """
            SELECT repo_full_name
            FROM mining_repo_cooldowns
            WHERE until_sequence >= ?
            ORDER BY repo_full_name
            """,
            (current_sequence,),
        )
    )


def decide(
    db: Database,
    settings: dict[str, object],
) -> ExplorationDecision:
    """Choose exploration capacity from unlabelled marginal-yield signals."""

    ensure_schema(db)

    last_batch = db.one(
        """
        SELECT batch_sequence, exploration_share
        FROM mining_controller_batches
        ORDER BY batch_sequence DESC
        LIMIT 1
        """
    )
    last_outcome = db.one(
        """
        SELECT MAX(batch_sequence) AS batch_sequence
        FROM mining_repo_batch_outcomes
        """
    ) or {"batch_sequence": 0}
    last_sequence = max(
        int(last_batch["batch_sequence"] or 0)
        if last_batch
        else 0,
        int(last_outcome["batch_sequence"] or 0),
    )
    current_sequence = (
        last_sequence + 1
    )

    floor = min(
        1.0,
        max(0.0, _float_setting(settings, "exploration_floor", 0.20)),
    )
    ceiling = min(
        1.0,
        max(floor, _float_setting(settings, "exploration_ceiling", 0.80)),
    )
    bootstrap = min(
        ceiling,
        max(floor, _float_setting(settings, "exploration_bootstrap", 0.30)),
    )
    step = min(
        1.0,
        max(0.01, _float_setting(settings, "exploration_step", 0.15)),
    )
    low_yield_rate = max(
        0.0,
        _float_setting(settings, "low_yield_rate", 0.05),
    )
    duplicate_threshold = min(
        1.0,
        max(0.0, _float_setting(settings, "duplicate_threshold", 0.80)),
    )
    minimum_records = max(
        1,
        _int_setting(settings, "saturation_min_records", 20),
    )
    low_batches = max(
        2,
        _int_setting(settings, "low_yield_batches", 2),
    )

    cooldown_repos = _refresh_cooldowns(
        db,
        current_sequence=current_sequence,
        settings=settings,
    )

    known_repo_row = db.one("SELECT COUNT(*) AS n FROM repos") or {"n": 0}
    known_repo_count = int(known_repo_row["n"] or 0)
    available_known = max(0, known_repo_count - len(cooldown_repos))

    recent = _recent_exploitation_batches(db, low_batches)
    last_share = (
        float(last_batch["exploration_share"])
        if last_batch
        else bootstrap
    )
    known_processed = sum(int(row["processed"] or 0) for row in recent)
    known_new_candidates = sum(
        int(row["new_candidates"] or 0)
        for row in recent
    )
    known_duplicate_prs = sum(
        int(row["duplicate_prs"] or 0)
        for row in recent
    )

    if known_repo_count == 0 or available_known == 0:
        share = 1.0
        reason = "no_available_known_repositories"
    elif len(recent) < low_batches:
        share = bootstrap
        reason = "cold_start"
    else:
        chronological = list(reversed(recent))
        batch_rates = [
            (
                int(row["new_candidates"] or 0)
                / int(row["processed"] or 1)
            )
            if int(row["processed"] or 0) > 0
            else 0.0
            for row in chronological
        ]
        enough_evidence = all(
            int(row["processed"] or 0) >= minimum_records
            for row in chronological
        )
        pr_total = sum(
            int(row["duplicate_prs"] or 0)
            + int(row["new_prs"] or 0)
            for row in chronological
        )
        duplicate_rate = (
            known_duplicate_prs / pr_total
            if pr_total
            else 0.0
        )
        diminishing = (
            enough_evidence
            and all(rate <= low_yield_rate for rate in batch_rates)
        )
        duplicate_saturated = (
            enough_evidence
            and duplicate_rate >= duplicate_threshold
        )
        improving = (
            enough_evidence
            and batch_rates[-1] > batch_rates[-2]
            and duplicate_rate < duplicate_threshold
        )

        if diminishing or duplicate_saturated:
            share = min(ceiling, last_share + step)
            reason = (
                "duplicate_saturation"
                if duplicate_saturated
                else "known_pool_diminishing_returns"
            )
        elif improving:
            share = max(floor, last_share - min(step, 0.10))
            reason = "known_pool_yield_improving"
        else:
            share = min(ceiling, max(floor, last_share))
            reason = "hold"

    return ExplorationDecision(
        batch_sequence=current_sequence,
        exploration_share=share,
        reason=reason,
        known_processed=known_processed,
        known_new_candidates=known_new_candidates,
        known_duplicate_prs=known_duplicate_prs,
        cooldown_repos=cooldown_repos,
    )


def allocate_lanes(
    *,
    shard_count: int,
    exploration_share: float,
) -> list[tuple[str, int, int]]:
    """Return (lane, lane-local index, lane-local count) per task shard."""

    shard_count = max(1, int(shard_count))
    share = min(1.0, max(0.0, float(exploration_share)))

    if share >= 1.0:
        explore_count = shard_count
    elif shard_count == 1:
        explore_count = 1 if share >= 0.5 else 0
    else:
        explore_count = max(
            1,
            min(shard_count - 1, round(shard_count * share)),
        )

    exploit_count = shard_count - explore_count
    lanes: list[tuple[str, int, int]] = []

    for shard_index in range(shard_count):
        if shard_index < explore_count:
            lanes.append(("explore", shard_index, explore_count))
        else:
            lanes.append(
                (
                    "exploit",
                    shard_index - explore_count,
                    exploit_count,
                )
            )

    return lanes


def record_decision(
    db: Database,
    *,
    batch_id: str,
    decision: ExplorationDecision,
    exploration_shards: int,
    exploitation_shards: int,
) -> None:
    ensure_schema(db)
    db.execute(
        """
        INSERT OR IGNORE INTO mining_controller_batches(
            batch_id,
            batch_sequence,
            exploration_share,
            exploration_shards,
            exploitation_shards,
            known_processed,
            known_new_candidates,
            known_duplicate_prs,
            reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_id,
            decision.batch_sequence,
            decision.exploration_share,
            exploration_shards,
            exploitation_shards,
            decision.known_processed,
            decision.known_new_candidates,
            decision.known_duplicate_prs,
            decision.reason,
        ),
    )
