from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ActionKey:
    action_id: int
    x: int = -1
    y: int = -1


class ActionBank:
    """Canonical reversible action encoding for ARC's mixed action space."""

    def __init__(self, click_action_id: int = 6, click_size: int = 64, max_action_id: int = 7):
        self.click_action_id = int(click_action_id)
        self.click_size = int(click_size)
        self.max_action_id = int(max_action_id)
        self.action_dim = self.max_action_id + 3  # one-hot ids + x + y + coordinate-valid flag

    def encode(self, a: ActionKey) -> np.ndarray:
        v = np.zeros(self.action_dim, dtype=np.float32)
        if not 1 <= int(a.action_id) <= self.max_action_id:
            raise ValueError(f"Unsupported action id {a.action_id}")
        v[int(a.action_id) - 1] = 1.0
        if int(a.action_id) == self.click_action_id:
            if not (0 <= int(a.x) < self.click_size and 0 <= int(a.y) < self.click_size):
                raise ValueError(f"Invalid click coordinate {(a.x, a.y)}")
            denom = max(1, self.click_size - 1)
            v[self.max_action_id] = float(a.x) / denom
            v[self.max_action_id + 1] = float(a.y) / denom
            v[self.max_action_id + 2] = 1.0
        return v

    def candidates(self, available: list[int] | tuple[int, ...]):
        out: list[ActionKey] = []
        for aid in sorted(set(int(x) for x in available)):
            if aid == self.click_action_id:
                for y in range(self.click_size):
                    for x in range(self.click_size):
                        out.append(ActionKey(aid, x, y))
            else:
                out.append(ActionKey(aid))
        return out

    def encode_candidates(self, available: list[int] | tuple[int, ...]):
        keys = self.candidates(available)
        if not keys:
            return keys, np.zeros((0, self.action_dim), dtype=np.float32)
        arr = np.stack([self.encode(a) for a in keys], axis=0)
        return keys, arr
