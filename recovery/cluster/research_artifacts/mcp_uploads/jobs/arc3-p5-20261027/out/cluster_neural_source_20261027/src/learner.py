"""Learner contract (the single seam between the adapter/run controller and any algorithm) + random policies."""
from __future__ import annotations

from typing import Optional, Protocol

import numpy as np

from .adapter import Observation, Transition, sample_flat_uniform, sample_type_uniform


class Learner(Protocol):
    def start_run(self, seed: int) -> None: ...
    def act(self, obs: Observation) -> int: ...
    def observe(self, t: Transition) -> None: ...            # always called before the next act()
    def finish(self, final_obs: Optional[Observation]) -> None: ...
    def diagnostics(self) -> dict: ...
    def state_dict(self) -> dict: ...
    def load_state_dict(self, d: dict) -> None: ...


class RandomPolicy:
    """Reference policies (plan 5.3): flat-uniform over legal indices, or type-uniform. No learning."""

    def __init__(self, mode: str):
        assert mode in ("type", "flat")
        self._sample = sample_type_uniform if mode == "type" else sample_flat_uniform
        self.name = f"random_{mode}"

    def start_run(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    def act(self, obs: Observation) -> int:
        return self._sample(self.rng, obs.mask)

    def observe(self, t: Transition) -> None: ...
    def finish(self, final_obs) -> None: ...
    def diagnostics(self) -> dict: return {}
    def state_dict(self) -> dict: return {}
    def load_state_dict(self, d: dict) -> None: ...
