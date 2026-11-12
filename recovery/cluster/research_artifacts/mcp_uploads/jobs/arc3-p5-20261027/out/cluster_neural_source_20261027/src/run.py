"""Run controller: owns budget, stopping, checkpoints, logging and scoring. Never touches model internals."""
from __future__ import annotations

import json
import platform
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .adapter import ArcSession, BaseSession, N_SIMPLE, N_TYPES, action_type
from .config import RunConfig, identity
from .learner import Learner, RandomPolicy


def build_learner(cfg: RunConfig) -> Learner:
    c = cfg.resolved()
    if c.algo == "random_type":
        return RandomPolicy("type")
    if c.algo == "random_flat":
        return RandomPolicy("flat")
    if c.algo == "dqn":
        if c.version.upper() == "V1":
            from .dqn_v1 import DQNV1
            return DQNV1(c.game, c.params, c.updates_disabled)
        from .dqn import DQN
        return DQN(c.arch, c.params, c.updates_disabled)
    if c.algo == "ppo":
        from .ppo import PPO
        return PPO(c.arch, c.params, c.updates_disabled)
    raise ValueError(c.algo)


def make_session(cfg: RunConfig, arc=None) -> BaseSession:
    if cfg.game.startswith("synthetic:"):
        from .synthetic import SyntheticSession
        return SyntheticSession(cfg.game.split(":", 1)[1])
    return ArcSession(arc)


def _background_cpu_pct() -> float:
    """System-wide CPU load just before the run: timings taken on a busy machine are pessimistic."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.5)
    except ImportError:
        return float("nan")


def _peak_mb() -> float:
    try:
        import psutil
        mi = psutil.Process().memory_info()
        return round(getattr(mi, "peak_wset", mi.rss) / 2**20, 1)
    except ImportError:
        return float("nan")


class RunStats:
    """Per-run diagnostics. Frame change, new state and repeated state are distinct measurements (plan 7.2)."""

    def __init__(self):
        self.type_counts = np.zeros(N_TYPES, dtype=np.int64)
        self.visited: set = set()
        self.frame_changes = self.new_states = self.repeated_state_transitions = 0
        self.rewarded = 0
        self.first_reward_action: Optional[int] = None
        self.curve: list = [(0, 0)]          # (actions used, high-water)
        self.game_overs = self.wins = 0
        self.n = 0
        self.actions: list = []

    def add(self, t, actions_used: int) -> None:
        self.n += 1
        self.actions.append(t.action)
        self.type_counts[action_type(t.action)] += 1
        self.frame_changes += bool(t.info["frame_changed"])
        key = t.next_obs.frame.tobytes()
        if key in self.visited:
            self.repeated_state_transitions += 1
        else:
            self.visited.add(key)
            self.new_states += 1
        if t.reward > 0:
            self.rewarded += 1
            if self.first_reward_action is None:
                self.first_reward_action = actions_used
            self.curve.append((actions_used, t.next_obs.high_water))
        self.game_overs += t.info["state"] == "GAME_OVER"
        self.wins += t.info["state"] == "WIN"

    def summary(self) -> dict:
        n = max(self.n, 1)
        return {"steps": self.n, "action_type_counts": self.type_counts.tolist(),
                "click_fraction": float(self.type_counts[N_SIMPLE] / n),
                "frame_change_rate": self.frame_changes / n, "unique_state_rate": self.new_states / n,
                "unique_states": self.new_states, "repeated_state_transitions": self.repeated_state_transitions,
                "rewarded_transitions": self.rewarded, "first_reward_action": self.first_reward_action,
                "progress_curve": self.curve, "game_overs": self.game_overs, "wins": self.wins}


def run(cfg: RunConfig, arc=None, out_dir: Optional[str] = None, session: Optional[BaseSession] = None,
        learner: Optional[Learner] = None, save_checkpoint: bool = False) -> dict:
    cfg = cfg.resolved()
    if cfg.threads:
        import torch
        torch.set_num_threads(cfg.threads)
    session = session or make_session(cfg, arc)
    learner = learner or build_learner(cfg)
    learner.start_run(cfg.seed)
    stats = RunStats()
    bg_cpu = _background_cpu_pct()
    t_env = t_act = t_obs = 0.0
    wall0 = time.perf_counter()
    error = None
    session.start_run(cfg.game.split(":", 1)[-1], cfg.budget, cfg.env_seed)
    try:
        while not session.done:
            t0 = time.perf_counter()
            a = learner.act(session.obs)
            t1 = time.perf_counter()
            tr = session.step(a)
            t2 = time.perf_counter()
            learner.observe(tr)
            t3 = time.perf_counter()
            t_act += t1 - t0
            t_env += t2 - t1
            t_obs += t3 - t2
            stats.add(tr, session.tracker.actions)
        t3 = time.perf_counter()
        learner.finish(session.obs)
        t_obs += time.perf_counter() - t3
    except Exception as e:                                   # interface errors are recorded, not hidden
        error = f"{type(e).__name__}: {e}"
        session.status = "error"
    wall = time.perf_counter() - wall0
    card = session.scorecard()
    tk = session.tracker
    ident = identity(cfg, getattr(learner, "model_info", lambda: {})())
    record = {
        "identity": ident,
        "status": session.status, "error": error,
        "counters": {"budget": cfg.budget, "scorer_actions": tk.actions, "env_commands": tk.env_commands,
                     "resets": tk.resets, "episodes": tk.episode + 1, "high_water": tk.high_water,
                     "sdk_total_actions": (card or {}).get("total_actions")},
        "official_score": ({"source": "arc_agi SDK local scorecard (NORMAL mode)", "score": card.get("score"),
                            "levels_completed": card.get("total_levels_completed"),
                            "arc_agi_version": ident["packages"]["arc-agi"]} if card else None),
        "diagnostics": stats.summary(),
        "learner": learner.diagnostics(),
        "cost": {"wall_s": round(wall, 2), "env_s": round(t_env, 2), "act_s": round(t_act, 2),
                 "observe_update_s": round(t_obs, 2), "peak_rss_mb": _peak_mb(),
                 "s_per_10k_actions": round(wall / max(tk.actions, 1) * 1e4, 1),
                 "host": platform.platform(), "threads": cfg.threads or "default",
                 "system_cpu_pct_before_run": bg_cpu},
        "scorecard": card,
    }
    if out_dir:
        d = Path(out_dir) / ident["run_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "record.json").write_text(json.dumps(record, indent=1, default=float))
        np.save(d / "actions.npy", np.asarray(stats.actions, dtype=np.int16))
        if save_checkpoint:
            save_ckpt(d / "checkpoint.pt", cfg, learner)
    record["_learner"] = learner
    return record


# ---------------------------------------------------------------- checkpoints
def save_ckpt(path, cfg: RunConfig, learner: Learner) -> None:
    import torch
    cfg = cfg.resolved()
    torch.save({"identity": identity(cfg, getattr(learner, "model_info", lambda: {})()),
                "config": cfg.to_dict(), "state": learner.state_dict()}, path)


def load_ckpt(path) -> tuple:
    """Rebuild the exact architecture/algorithm from the stored config, then load weights."""
    import torch
    blob = torch.load(path, weights_only=False)
    cfg = RunConfig.from_dict(blob["config"])
    assert cfg.hash() == blob["identity"]["config_hash"], "config hash mismatch"
    learner = build_learner(cfg)
    learner.start_run(cfg.seed)
    learner.load_state_dict(blob["state"])
    return cfg, learner
