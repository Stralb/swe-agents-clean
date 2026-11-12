from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass
class StepTransition:
    state: np.ndarray
    available: tuple[int, ...]
    action: np.ndarray
    action_key: tuple[int, int, int]
    reward: float
    next_state: np.ndarray
    next_available: tuple[int, ...]
    terminal: bool


@dataclass
class ReplayTransition:
    state: np.ndarray
    available: tuple[int, ...]
    action: np.ndarray
    action_key: tuple[int, int, int]
    reward: float
    next_state: np.ndarray
    next_available: tuple[int, ...]
    terminal: bool
    gamma_n: float
    n_steps: int


class NStepAccumulator:
    def __init__(self, n_step: int, gamma: float):
        self.n_step = int(n_step)
        self.gamma = float(gamma)
        self.q: deque[StepTransition] = deque()

    def _emit_one(self) -> ReplayTransition:
        reward = 0.0
        gamma = 1.0
        terminal = False
        last = self.q[0]
        used = 0
        for t in self.q:
            reward += gamma * float(t.reward)
            used += 1
            last = t
            terminal = bool(t.terminal)
            if terminal or used >= self.n_step:
                break
            gamma *= self.gamma
        first = self.q[0]
        self.q.popleft()
        return ReplayTransition(
            state=first.state,
            available=first.available,
            action=first.action,
            action_key=first.action_key,
            reward=reward,
            next_state=last.next_state,
            next_available=last.next_available,
            terminal=terminal,
            gamma_n=self.gamma ** used,
            n_steps=used,
        )

    def append(self, t: StepTransition) -> list[ReplayTransition]:
        self.q.append(t)
        out: list[ReplayTransition] = []
        if len(self.q) >= self.n_step:
            out.append(self._emit_one())
        if t.terminal:
            while self.q:
                out.append(self._emit_one())
        return out

    def flush(self) -> list[ReplayTransition]:
        out = []
        while self.q:
            out.append(self._emit_one())
        return out


class ReplayBuffer:
    def __init__(self, capacity: int, prioritized: bool, alpha: float, eps: float):
        self.capacity = int(capacity)
        self.prioritized = bool(prioritized)
        self.alpha = float(alpha)
        self.eps = float(eps)
        self.data: list[ReplayTransition] = []
        self.priorities = np.zeros(self.capacity, dtype=np.float64)
        self.pos = 0

    def __len__(self) -> int:
        return len(self.data)

    def add(self, t: ReplayTransition) -> None:
        p = float(self.priorities[: len(self.data)].max()) if self.data else 1.0
        if len(self.data) < self.capacity:
            self.data.append(t)
        else:
            self.data[self.pos] = t
        self.priorities[self.pos] = max(p, self.eps)
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size: int, beta: float, rng: random.Random):
        n = len(self.data)
        if n < batch_size:
            raise ValueError(f"replay has {n}, need {batch_size}")
        if self.prioritized:
            p = self.priorities[:n].copy()
            p = np.maximum(p, self.eps) ** self.alpha
            p /= p.sum()
            idx = np.asarray(rng.choices(range(n), weights=p.tolist(), k=batch_size), dtype=np.int64)
            w = (n * p[idx]) ** (-float(beta))
            w /= max(w.max(), 1e-12)
        else:
            idx = np.asarray(rng.sample(range(n), batch_size), dtype=np.int64)
            w = np.ones(batch_size, dtype=np.float64)
        return idx, [self.data[int(i)] for i in idx], w.astype(np.float32)

    def update_priorities(self, idx: Iterable[int], values: Iterable[float]) -> None:
        for i, v in zip(idx, values):
            self.priorities[int(i)] = max(abs(float(v)) + self.eps, self.eps)
