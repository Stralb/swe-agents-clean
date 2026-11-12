"""Phase 1 random reference agent for the ARC-AGI-3 Kaggle submission path.

Follows the ARC-AGI-3-Kaggle-Starter contract (subclass `agents.agent.Agent`, class named `MyAgent`,
`is_done` + `choose_action`). Uses only `latest_frame.available_actions` and the frame state, i.e.
information permitted by the evaluation interface. No learning, no per-game logic.

MODE = "type_uniform": pick uniformly among available action types (ACTION6 = one type), then a uniform
                        (x, y) if ACTION6.
MODE = "flat_uniform" : pick uniformly over the flattened legal space (each simple action + 4096 clicks);
                        clicks dominate whenever ACTION6 is available (plan 5.3).
"""
from __future__ import annotations

import random
from typing import Any

from arcengine import FrameData, GameAction, GameState

from agents.agent import Agent

MODE = "type_uniform"
SEED = 0
GRID = 64
# Provisional: real competition action limit / runtime must be checked on Kaggle (docs/DECISIONS.md).
RANDOM_MAX_ACTIONS = 1000


def sample_action(rng: random.Random, available: list[int], mode: str) -> tuple[int, tuple[int, int] | None]:
    """Return (action_id, (x, y) or None) from the legal set. RESET (0) is never sampled."""
    legal = [a for a in available if a != 0]
    if not legal:
        raise ValueError("no legal actions")
    simple = [a for a in legal if a != 6]
    has_click = 6 in legal
    if mode == "type_uniform":
        a = rng.choice(legal)
    elif mode == "flat_uniform":
        k = rng.randrange(len(simple) + (GRID * GRID if has_click else 0))
        a = simple[k] if k < len(simple) else 6
    else:
        raise ValueError(mode)
    return (a, (rng.randrange(GRID), rng.randrange(GRID))) if a == 6 else (a, None)


class MyAgent(Agent):
    MAX_ACTIONS = RANDOM_MAX_ACTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.mode = MODE
        self.rng = random.Random(f"{SEED}-{self.game_id.split('-')[0]}")

    @property
    def name(self) -> str:
        return f"{super().name}.random-{self.mode}.{self.MAX_ACTIONS}"

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        if latest_frame.state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            return GameAction.RESET
        a, xy = sample_action(self.rng, list(latest_frame.available_actions), self.mode)
        action = GameAction.from_id(a)
        if xy is not None:
            action.set_data({"x": xy[0], "y": xy[1]})
        action.reasoning = f"random {self.mode}"
        return action
