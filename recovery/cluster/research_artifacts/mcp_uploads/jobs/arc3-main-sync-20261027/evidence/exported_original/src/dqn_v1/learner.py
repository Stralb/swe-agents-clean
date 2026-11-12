"""Team Learner adapter for the experimentally selected DQN V1 baseline."""
from __future__ import annotations

import random
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from ..adapter import N_SIMPLE, SIMPLE_IDS, Observation, Transition, action_to_index, index_to_action
from .action_bank import ActionKey
from .agent import DQNAgent
from .exploration import SELECTOR, StructuredExplorer
from .prior import PUBLIC_GAMES, load_prior, state_outputs

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "dqn_v1"

SYSTEM = {
    "id": "dqn_v1_selected",
    "family": "selected_baseline",
    "learn": True,
    "n_step": 1,
    "per": False,
    "distributional": False,
    "dueling": True,
    "exploration_policy": "d14",
    "structured_probability": 1.0,
}


def _available(mask: np.ndarray) -> list[int]:
    out = [aid for i, aid in enumerate(SIMPLE_IDS) if bool(mask[i])]
    if bool(mask[N_SIMPLE:].any()):
        out.append(6)
    return sorted(out)


def _to_index(a: ActionKey) -> int:
    return action_to_index(int(a.action_id), (int(a.x), int(a.y)) if int(a.action_id) == 6 else None)


def _from_index(idx: int) -> ActionKey:
    aid, xy = index_to_action(int(idx))
    return ActionKey(aid, *(xy or (-1, -1)))


class DQNV1:
    name = "dqn_v1"

    def __init__(self, game: str, params: dict, updates_disabled: bool = False):
        self.game = game
        self.p = dict(params)
        self.updates_disabled = bool(updates_disabled)
        self.device = torch.device("cpu")

    def _cfg(self):
        return {
            "click_action_id": 6,
            "click_size": 64,
            "max_action_id": 7,
            "training": self.p,
        }

    def start_run(self, seed: int) -> None:
        if self.game not in PUBLIC_GAMES:
            # The exact selected result used cross-fold public checkpoints. Do not
            # silently pretend one of them is a hidden-game deployment model.
            load_prior(self.game, ASSETS, self.device)
        self.seed = int(seed)
        self.prior, self.fold, self.checkpoint = load_prior(self.game, ASSETS, self.device)
        game_idx = PUBLIC_GAMES.index(self.game)
        run_seed = self.seed * 100003 + game_idx * 9173
        random.seed(run_seed); np.random.seed(run_seed & 0xFFFFFFFF); torch.manual_seed(run_seed)
        self.explorer = StructuredExplorer()
        self.system = dict(SYSTEM)
        if self.updates_disabled:
            self.system["learn"] = False
        self.agent = DQNAgent(130, self.system, self._cfg(), run_seed + 17, self.device)
        self.pending = None
        self.last_label = None
        self.since_progress = 0

    def _features(self, obs: Observation):
        available = _available(obs.mask)
        emb, simple, simple_logits, a6_logits = state_outputs(
            self.prior, obs.frame, obs.prev_frame, available, self.device
        )
        state = np.concatenate([
            emb.reshape(-1),
            np.asarray([obs.progress / 5.0, obs.high_water / 5.0], dtype=np.float32),
        ]).astype(np.float32)
        return state, emb, simple, simple_logits, a6_logits, available

    def act(self, obs: Observation) -> int:
        state, emb, simple, simple_logits, a6_logits, available = self._features(obs)

        def explore_fn(rng, action_index):
            return self.explorer.choose(rng, available, obs.frame, simple, simple_logits, a6_logits)

        action, label = self.agent.act(state, available, explore_fn=explore_fn)
        self.explorer.observe(obs.frame, action)  # counts greedy actions too, matching the selected experiment
        idx = _to_index(action)
        self.pending = (state, tuple(available), action, idx)
        self.last_label = label
        return idx

    def observe(self, t: Transition) -> None:
        if self.pending is None:
            raise RuntimeError("observe() called without a pending V1 action")
        state, available, action, idx = self.pending
        if int(t.action) != int(idx):
            raise AssertionError(("V1 pending action mismatch", idx, t.action))

        reward = float(t.reward)
        if t.info.get("state") == "WIN" and reward == 0.0:
            reward = 1.0  # exact selected-baseline reward convention

        if t.terminal:
            next_state = state.copy()
            next_available = tuple()
        else:
            next_state, _, _, _, _, nav = self._features(t.next_obs)
            next_available = tuple(nav)

        self.agent.observe(state, available, action, reward, next_state, next_available, bool(t.terminal))
        if reward > 0 or t.info.get("state") == "WIN":
            self.since_progress = 0
        else:
            self.since_progress += 1
        self.pending = None

    def finish(self, final_obs: Optional[Observation]) -> None:
        self.agent.finish()

    def diagnostics(self) -> dict:
        return {
            "algo": "dqn",
            "version": "V1",
            "selected_system": SYSTEM["id"],
            "fold": self.fold,
            "prior_checkpoint": str(self.checkpoint.relative_to(ROOT)),
            "selector": SELECTOR["id"],
            **self.agent.summary(),
        }

    def model_info(self) -> dict:
        return {
            "architecture": "selected_onehot_stack2_vector_effect+dueling_action_value",
            "parameters": sum(p.numel() for p in self.agent.online.parameters()),
            "frozen_prior_parameters": sum(p.numel() for p in self.prior.parameters()),
            "action_representation": "shared 10-D action vector over the legal action set",
            "auxiliary_objectives": ["frozen binary action-effect prior"],
            "memory": "downsample16 state-action counts inside structured epsilon exploration",
            "checkpoint_mode": "public cross-fold, seed-11 prior (faithful final-ablation reproduction)",
        }

    def state_dict(self) -> dict:
        return {
            "online": self.agent.online.state_dict(),
            "target": self.agent.target.state_dict(),
            "optimizer": self.agent.optimizer.state_dict(),
            "action_count": self.agent.action_count,
            "stats": asdict(self.agent.stats),
            "replay_data": self.agent.replay.data,
            "replay_priorities": self.agent.replay.priorities,
            "replay_pos": self.agent.replay.pos,
            "epsilon_rng": self.agent.epsilon_rng.getstate(),
            "explore_rng": self.agent.explore_rng.getstate(),
            "replay_rng": self.agent.replay_rng.getstate(),
            "pair_counts": dict(self.explorer.pair_counts),
        }

    def load_state_dict(self, d: dict) -> None:
        self.agent.online.load_state_dict(d["online"])
        self.agent.target.load_state_dict(d["target"])
        self.agent.optimizer.load_state_dict(d["optimizer"])
        self.agent.action_count = int(d["action_count"])
        for k, v in d["stats"].items():
            setattr(self.agent.stats, k, v)
        self.agent.replay.data = list(d["replay_data"])
        self.agent.replay.priorities[:] = d["replay_priorities"]
        self.agent.replay.pos = int(d["replay_pos"])
        self.agent.epsilon_rng.setstate(d["epsilon_rng"])
        self.agent.explore_rng.setstate(d["explore_rng"])
        self.agent.replay_rng.setstate(d["replay_rng"])
        self.explorer.pair_counts.update(d["pair_counts"])
