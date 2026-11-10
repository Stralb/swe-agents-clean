"""Run configuration and experiment identity (plan 5.2 'Experiment identity').

A RunConfig is resolved once at run start: defaults are merged so the stored config is the *full* one, and the
config hash is stable. Nothing here is parsed per step.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from importlib.metadata import version
from pathlib import Path

SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[1]

# Provisional experiment settings from the plan (5.4 / 5.5). Configuration, not constraints; calibrate before freezing.
ARCH_DEFAULTS = {
    "onehotcnn_stack2": {"id": "onehotcnn_stack2", "channels": 32, "context_dim": 128},   # provisional V0
    "onehotcnn_stack1": {"id": "onehotcnn_stack1", "channels": 32, "context_dim": 128},   # current frame only
}
ALGO_DEFAULTS = {
    "dqn": {"lr": 1e-4, "gamma": 0.99, "batch": 32, "replay_capacity": 50_000, "warmup": 1_000,
            "train_every": 4, "target_update": 1_000, "eps_start": 1.0, "eps_end": 0.05,
            "eps_decay_actions": 10_000, "huber_delta": 1.0, "double": True, "grad_clip": 10.0},
    "ppo": {"rollout": 128, "epochs": 4, "minibatches": 4, "clip": 0.2, "lr": 2.5e-4, "gamma": 0.99,
            "gae_lambda": 0.95, "ent_coef": 0.01, "vf_coef": 0.5, "grad_clip": 0.5},
    "random_type": {}, "random_flat": {},
}
ALGOS = tuple(ALGO_DEFAULTS)

DQN_V1_DEFAULTS = {
    "gamma": 0.99,
    "learning_rate": 1e-4,
    "batch_size": 8,
    "replay_capacity": 4096,
    "warmup_actions": 16,
    "train_every_actions": 8,
    "target_update_actions": 80,
    "gradient_clip_norm": 10.0,
    "hidden_dim": 128,
    "epsilon_start": 1.0,
    "epsilon_end": 0.1,
    "epsilon_decay_actions": 400,
    "per_alpha": 0.6,
    "per_beta_start": 0.4,
    "per_beta_end": 1.0,
    "per_eps": 1e-4,
    "c51_atoms": 51,
    "c51_vmin": 0.0,
    "c51_vmax": 5.0,
}


@dataclass
class RunConfig:
    algo: str                                   # dqn | ppo | random_type | random_flat
    game: str                                   # short game id, or "synthetic:<task>"
    version: str = "V0"                         # V0 | V1 | V2 | A2 | ...
    seed: int = 0                               # learner/torch/numpy seed
    env_seed: int = 0                           # game seed (kept fixed: same game across seeds)
    budget: int = 1000                          # scorer-rule actions
    arch: dict = field(default_factory=lambda: dict(ARCH_DEFAULTS["onehotcnn_stack2"]))
    params: dict = field(default_factory=dict)  # overrides on ALGO_DEFAULTS
    updates_disabled: bool = False              # matched control: identical schedule, no gradient steps
    regime: str = "research"                    # research | competition (plan 7.1)
    threads: int = 0                            # torch threads; 0 = library default
    tag: str = ""                               # free-form note

    def resolved(self) -> "RunConfig":
        if self.algo not in ALGOS:
            raise ValueError(f"unknown algo {self.algo!r}")
        arch = {**ARCH_DEFAULTS[self.arch.get("id", "onehotcnn_stack2")], **self.arch}
        base_params = DQN_V1_DEFAULTS if self.algo == "dqn" and self.version.upper() == "V1" else ALGO_DEFAULTS[self.algo]
        params = {**base_params, **self.params}
        return RunConfig(**{**asdict(self), "arch": arch, "params": params})

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RunConfig":
        return cls(**d)

    def hash(self) -> str:
        blob = json.dumps(self.resolved().to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def run_id(self) -> str:
        return f"{self.algo}-{self.version}-{self.game.replace(':', '_')}-s{self.seed}-{self.hash()}"


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        return out + ("+dirty" if dirty else "")
    except OSError:
        return "unknown"


def _split_hash() -> str:
    try:
        return json.loads((ROOT / "configs" / "splits.json").read_text())["hash"]
    except (OSError, KeyError, ValueError):
        return "none"


def identity(cfg: RunConfig, model_info: dict | None = None) -> dict:
    """Everything needed to reproduce a run/checkpoint (plan 5.2)."""
    c = cfg.resolved()
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": c.run_id(),
        "config_hash": c.hash(),
        "config": c.to_dict(),
        "architecture_id": (model_info or {}).get("architecture", c.arch["id"]),
        "observation_contract": {"frame": "int8[64,64]", "history": "previous step's last frame",
                                 "extras": "prev_action, progress, high_water, mask"},
        "action_representation": (model_info or {}).get("action_representation", "flat4102: 6 simple + 4096 clicks; type-balanced exploration"),
        "auxiliary_objectives": (model_info or {}).get("auxiliary_objectives", []),
        "memory": (model_info or {}).get("memory"),
        "budget_accounting": "scorer-rule actions (steps + non-first resets)",
        "split_hash": _split_hash(),
        "code_commit": _git_commit(),
        "packages": {p: version(p) for p in ("arc-agi", "arcengine", "numpy", "torch")},
        "model_info": model_info or {},
    }
