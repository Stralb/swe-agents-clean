from __future__ import annotations

import tempfile
from pathlib import Path

from src.db.database import Database
from src.distributed.repo_exploration_controller import (
    ExplorationDecision,
    allocate_lanes,
    decide,
    ensure_schema,
    record_decision,
)


SETTINGS: dict[str, object] = {
    "exploration_floor": 0.20,
    "exploration_bootstrap": 0.30,
    "exploration_ceiling": 0.80,
    "exploration_step": 0.15,
    "low_yield_rate": 0.05,
    "duplicate_threshold": 0.80,
    "saturation_min_records": 20,
    "saturation_max_new_candidates": 1,
    "low_yield_batches": 2,
    "cooldown_batches": 3,
}


def _database(path: Path, repos: tuple[str, ...]) -> Database:
    db = Database(path, read_only=False, command_spool=None)
    db.execute(
        """
        CREATE TABLE repos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT UNIQUE NOT NULL
        )
        """
    )
    for repo in repos:
        db.execute(
            "INSERT INTO repos(full_name) VALUES (?)",
            (repo,),
        )
    ensure_schema(db)
    return db


def _record_batch(
    db: Database,
    *,
    sequence: int,
    share: float,
) -> None:
    record_decision(
        db,
        batch_id=f"mining-{sequence}",
        decision=ExplorationDecision(
            batch_sequence=sequence,
            exploration_share=share,
            reason="test",
            known_processed=0,
            known_new_candidates=0,
            known_duplicate_prs=0,
            cooldown_repos=(),
        ),
        exploration_shards=10,
        exploitation_shards=22,
    )


def _outcome(
    db: Database,
    *,
    sequence: int,
    repo: str,
    processed: int,
    new_candidates: int,
    new_prs: int = 0,
    seen_prs: int = 0,
) -> None:
    db.execute(
        """
        INSERT INTO mining_repo_batch_outcomes(
            task_id,
            batch_id,
            batch_sequence,
            lane,
            repo_full_name,
            processed_records,
            new_prs,
            already_seen_prs,
            new_unique_candidates
        )
        VALUES (?, ?, ?, 'exploit', ?, ?, ?, ?, ?)
        """,
        (
            f"task-{sequence}-{repo}",
            f"mining-{sequence}",
            sequence,
            repo,
            processed,
            new_prs,
            seen_prs,
            new_candidates,
        ),
    )


def test_empty_database_uses_all_workers_for_discovery() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = _database(Path(raw) / "test.db", ())
        decision = decide(db, SETTINGS)
        assert decision.exploration_share == 1.0
        assert decision.reason == "no_available_known_repositories"


def test_cold_start_uses_bootstrap_share() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = _database(
            Path(raw) / "test.db",
            ("one/repo",),
        )
        decision = decide(db, SETTINGS)
        assert decision.exploration_share == 0.30
        assert decision.reason == "cold_start"

        lanes = allocate_lanes(
            shard_count=32,
            exploration_share=decision.exploration_share,
        )
        assert sum(lane == "explore" for lane, _, _ in lanes) == 10
        assert sum(lane == "exploit" for lane, _, _ in lanes) == 22


def test_two_low_yield_batches_increase_exploration() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = _database(
            Path(raw) / "test.db",
            ("one/repo", "two/repo", "three/repo"),
        )
        _record_batch(db, sequence=1, share=0.30)
        _record_batch(db, sequence=2, share=0.30)

        for sequence in (1, 2):
            for repo in ("one/repo", "two/repo", "three/repo"):
                _outcome(
                    db,
                    sequence=sequence,
                    repo=repo,
                    processed=10,
                    new_candidates=0,
                    new_prs=10,
                )

        decision = decide(db, SETTINGS)
        assert decision.batch_sequence == 3
        assert abs(decision.exploration_share - 0.45) < 1e-9
        assert decision.reason == "known_pool_diminishing_returns"
        assert decision.cooldown_repos == ()


def test_repository_cools_down_then_requires_a_new_observation() -> None:
    with tempfile.TemporaryDirectory() as raw:
        db = _database(
            Path(raw) / "test.db",
            ("slow/repo", "healthy/repo"),
        )
        _record_batch(db, sequence=1, share=0.30)
        _record_batch(db, sequence=2, share=0.30)

        for sequence in (1, 2):
            _outcome(
                db,
                sequence=sequence,
                repo="slow/repo",
                processed=20,
                new_candidates=0,
                seen_prs=20,
            )
            _outcome(
                db,
                sequence=sequence,
                repo="healthy/repo",
                processed=20,
                new_candidates=5,
                new_prs=20,
            )

        decision = decide(db, SETTINGS)
        assert decision.batch_sequence == 3
        assert decision.cooldown_repos == ("slow/repo",)

        cooldown = db.one(
            """
            SELECT triggered_by_sequence, until_sequence
            FROM mining_repo_cooldowns
            WHERE repo_full_name='slow/repo'
            """
        )
        assert cooldown == {
            "triggered_by_sequence": 2,
            "until_sequence": 5,
        }
