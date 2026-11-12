"""Kaggle MyAgent that runs a DQN/PPO learner from `src/` through the ARC-AGI-3-Agents loop.

Phase 2 scaffold: proves the learner lifecycle works through the competition callback. Packaging `src/` into the
Kaggle notebook is a Phase 7 task (the notebook builder currently splices a single file).

Per game the framework builds a fresh MyAgent, so learned state persists between *actions* and *levels* of one game
(one live environment, online learning) and is discarded between games and runs (plan 4.2).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from arcengine import FrameData, GameAction, GameState

from agents.agent import Agent

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.bridge import ACT, FrameworkBridge, to_game_action   # noqa: E402
from src.config import RunConfig                              # noqa: E402
from src.run import build_learner                             # noqa: E402

# Overridable for tests / experiments; default is the provisional DQN V0 configuration.
CONFIG = json.loads(os.environ.get("ARC_LEARNER_CONFIG", "null")) or {"algo": "dqn", "game": "", "budget": 1000}


class MyAgent(Agent):
    MAX_ACTIONS = CONFIG.get("budget", 1000) - 1      # the framework loop runs MAX_ACTIONS + 1 iterations

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = RunConfig.from_dict({**CONFIG, "game": self.game_id})
        self.cfg = cfg.resolved()
        self.learner = build_learner(self.cfg)
        self.bridge = FrameworkBridge(self.learner, seed=self.cfg.seed)

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        kind, idx = self.bridge.choose(latest_frame)
        if kind != ACT:
            return GameAction.RESET
        action = to_game_action(idx)
        action.reasoning = f"{self.cfg.algo} {self.cfg.version}"
        return action

    def cleanup(self, *args, **kwargs) -> None:
        self.bridge.finish()
        super().cleanup(*args, **kwargs)
