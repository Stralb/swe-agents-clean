"""Synthetic learning checks (plan 6 'Learning checks before ARC experiments').

Implementation/correctness checks only, not architecture-selection benchmarks. They plug in below the adapter's
BaseSession, so reward (high-water), masks, resets, budget and logging use exactly the code paths ARC runs use.
They return NO official score (scorecard() is None), so they can never be mistaken for one.

    nav  : move a block to a fixed goal on a 5x5 board (keyboard actions 1-4); 30 steps per attempt, then GAME_OVER
    click: click the target square (colour 3) among distractors (colour 4); only ACTION6 legal
    cue  : two squares with different colours (3 and 4) at random positions; a far-away cue block (colour 5 or 6)
           says which colour is the target. Each square's appearance is visible locally but the cue is ~10+px
           away (receptive field is 9x9), so a policy that beats 0.5 hits per square-click must be using
           whole-board context. (Squares must differ in appearance: a translation-equivariant click head with
           one global vector cannot tell apart two locally identical squares by position.)
"""
from __future__ import annotations

import numpy as np

from .adapter import BaseSession, RawFrame

WIN_LEVELS = 10 ** 6


class _Task:
    available: list
    win_levels = WIN_LEVELS

    def __init__(self, seed: int):
        self.rng = np.random.default_rng(seed)
        self.levels = 0

    def _raw(self, frame, state="NOT_FINISHED") -> RawFrame:
        return RawFrame([frame], state, self.levels, self.win_levels, list(self.available))


class NavTask(_Task):
    available = [1, 2, 3, 4]
    G, CELL, LIMIT = 5, 12, 30
    GOAL = (4, 4)

    def _new_level(self):
        while True:
            self.pos = [int(self.rng.integers(self.G)), int(self.rng.integers(self.G))]
            if tuple(self.pos) != self.GOAL:
                break
        self.t = 0

    def _draw(self):
        f = np.zeros((64, 64), np.int8)
        c = self.CELL
        f[self.GOAL[1] * c + 2:(self.GOAL[1] + 1) * c + 2, self.GOAL[0] * c + 2:(self.GOAL[0] + 1) * c + 2] = 2
        f[self.pos[1] * c + 2:(self.pos[1] + 1) * c + 2, self.pos[0] * c + 2:(self.pos[0] + 1) * c + 2] = 1
        return f

    def reset(self) -> RawFrame:
        self._new_level()
        return self._raw(self._draw())

    def send(self, aid, xy) -> RawFrame:
        dx, dy = {1: (0, -1), 2: (0, 1), 3: (-1, 0), 4: (1, 0)}[aid]
        self.pos = [min(max(self.pos[0] + dx, 0), self.G - 1), min(max(self.pos[1] + dy, 0), self.G - 1)]
        self.t += 1
        if tuple(self.pos) == self.GOAL:
            self.levels += 1
            self._new_level()
            return self._raw(self._draw())
        return self._raw(self._draw(), "GAME_OVER" if self.t >= self.LIMIT else "NOT_FINISHED")


class ClickTask(_Task):
    available = [6]
    S = 12

    def _new_level(self):
        S = self.S
        boxes = []
        while len(boxes) < 3:                                       # target + 2 distractors, non-overlapping
            x, y = (int(v) for v in self.rng.integers(0, 64 - S, 2))
            if all(abs(x - a) >= S or abs(y - b) >= S for a, b in boxes):
                boxes.append((x, y))
        self.target, self.dis = boxes[0], boxes[1:]

    def _draw(self):
        f = np.zeros((64, 64), np.int8)
        for (x, y) in self.dis:
            f[y:y + self.S, x:x + self.S] = 4
        x, y = self.target
        f[y:y + self.S, x:x + self.S] = 3
        return f

    def reset(self) -> RawFrame:
        self._new_level()
        return self._raw(self._draw())

    def send(self, aid, xy) -> RawFrame:
        x, y = xy
        tx, ty = self.target
        if tx <= x < tx + self.S and ty <= y < ty + self.S:
            self.levels += 1
            self._new_level()
        return self._raw(self._draw())


class CueTask(_Task):
    available = [6]
    S = 12
    MIN_ROW = 16                                                    # keeps squares far from the cue block (rows 2..5)

    def _new_level(self):
        S = self.S
        boxes = []
        while len(boxes) < 2:
            x = int(self.rng.integers(0, 64 - S))
            y = int(self.rng.integers(self.MIN_ROW, 64 - S))
            if all(abs(x - a) >= S or abs(y - b) >= S for a, b in boxes):
                boxes.append((x, y))
        self.boxes = boxes                                          # boxes[0] has colour 3, boxes[1] colour 4
        self.cue = int(self.rng.integers(2))                        # 0 -> cue colour 5 -> colour-3 square is correct

    def _draw(self):
        f = np.zeros((64, 64), np.int8)
        f[2:6, 2:6] = 5 + self.cue
        for colour, (x, y) in zip((3, 4), self.boxes):
            f[y:y + self.S, x:x + self.S] = colour
        return f

    def reset(self) -> RawFrame:
        self._new_level()
        return self._raw(self._draw())

    def send(self, aid, xy) -> RawFrame:
        x, y = xy
        cx, cy = self.boxes[self.cue]
        if cx <= x < cx + self.S and cy <= y < cy + self.S:
            self.levels += 1
            self._new_level()
        return self._raw(self._draw())


TASKS = {"nav": NavTask, "click": ClickTask, "cue": CueTask}


class SyntheticSession(BaseSession):
    def __init__(self, task: str):
        super().__init__()
        self.task_name = task

    def _open(self, game: str, env_seed: int) -> None:
        self.task = TASKS[self.task_name](env_seed)

    def _send(self, action_id, xy) -> RawFrame:
        return self.task.send(action_id, xy)

    def _reset(self) -> RawFrame:
        return self.task.reset()
