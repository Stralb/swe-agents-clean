"""ARC-AGI-3 generic event-terminated exploration agent (E075 -> Kaggle adaptation).

The agent uses only current/previous public 64x64 frames and legal actions. No
hidden state, environment IDs, demonstration traces, copied action scripts,
or network access. This is a hand-coded exploration reference, NOT DQN/PPO.

Research provenance: E075 event-terminated interaction procedures (Oct 2026).
Native single-development-game result: vc33, 2/7 levels in three policy seeds.
No leaderboard score is claimed, and other-game generalisation is untested.
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from typing import Any

import numpy as np
from arcengine import FrameData, GameAction, GameState
from agents.agent import Agent

GRID = 64
SIMPLE_IDS = (1, 2, 3, 4, 5, 7)
N_SIMPLE = 6
N_ACTIONS = N_SIMPLE + GRID * GRID
SEED = 28901


def digest(a: np.ndarray) -> bytes:
    return hashlib.blake2b(np.asarray(a, dtype=np.int8).tobytes(), digest_size=12).digest()


def candidate_points(frame: np.ndarray, limit: int = 140) -> list[tuple[int, int]]:
    f = np.asarray(frame, dtype=np.uint8)
    if f.shape != (64, 64):
        return [(x, y) for y in range(4, 64, 8) for x in range(4, 64, 8)][:limit]
    colours, count = np.unique(f, return_counts=True)
    bg = int(colours[int(np.argmax(count))])
    seen = np.zeros((64, 64), dtype=bool)
    components = []
    for colour in colours:
        c = int(colour)
        if c == bg:
            continue
        for y in range(64):
            for x in range(64):
                if seen[y, x] or int(f[y, x]) != c:
                    continue
                todo = [(y, x)]
                seen[y, x] = True
                pixels = []
                while todo:
                    yy, xx = todo.pop()
                    pixels.append((yy, xx))
                    for ny, nx in ((yy-1, xx), (yy+1, xx), (yy, xx-1), (yy, xx+1)):
                        if 0 <= ny < 64 and 0 <= nx < 64 and not seen[ny, nx] and int(f[ny, nx]) == c:
                            seen[ny, nx] = True
                            todo.append((ny, nx))
                components.append((len(pixels), c, pixels))
    components.sort(key=lambda entry: (entry[0] > 160, abs(entry[0] - 8), entry[1], entry[2][0]))
    coords, known = [], set()

    def add(x: int, y: int):
        if 0 <= x < 64 and 0 <= y < 64 and (x, y) not in known:
            known.add((x, y))
            coords.append((x, y))

    for _, col, pixels in components[:100]:
        cy = sum(p[0] for p in pixels) / len(pixels)
        cx = sum(p[1] for p in pixels) / len(pixels)
        samples = [min(pixels, key=lambda p: (p[0]-cy)**2 + (p[1]-cx)**2),
                   min(pixels, key=lambda p: p[0]), max(pixels, key=lambda p: p[0]),
                   min(pixels, key=lambda p: p[1]), max(pixels, key=lambda p: p[1])]
        for yy, xx in samples:
            add(xx, yy)
    if len(coords) < limit:
        for y in range(4, 64, 8):
            for x in range(4, 64, 8):
                add(x, y)
    return coords[:limit]


def ids_to_mask(available) -> np.ndarray:
    av = set(map(int, available))
    mask = np.zeros(N_ACTIONS, dtype=bool)
    for i, id_ in enumerate(SIMPLE_IDS):
        mask[i] = id_ in av
    mask[N_SIMPLE:] = 6 in av
    return mask


class EventRepeat:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.visits = Counter()
        self.model = {}
        self.active = None
        self.consecutive = 0
        self.stats = Counter()

    def select(self, frame: np.ndarray, mask: np.ndarray) -> tuple[int, str]:
        if self.active is not None and mask[self.active]:
            self.stats['option_steps'] += 1
            return self.active, 'repeat_until_effect_stops'
        candidates = list(map(int, np.flatnonzero(mask[:N_SIMPLE])))
        if bool(mask[N_SIMPLE:].any()):
            candidates.extend(N_SIMPLE + y * GRID + x
                              for x, y in candidate_points(frame)
                              if mask[N_SIMPLE + y * GRID + x])
        if not candidates:
            candidates = list(map(int, np.flatnonzero(mask)))
        if not candidates:
            raise RuntimeError('No legal actions')
        candidates = sorted(set(candidates))
        key = digest(frame)
        self.rng.shuffle(candidates)
        minimum = min(self.visits[(key, i)] for i in candidates)
        a = self.rng.choice([i for i in candidates if self.visits[(key, i)] == minimum])
        self.stats['new_probes'] += 1
        return a, 'new_object_probe'

    def observe(self, previous: np.ndarray, after: np.ndarray, index: int,
                reason: str, level_up: bool = False, terminal: bool = False):
        before = np.asarray(previous, dtype=np.int8)
        after = np.asarray(after, dtype=np.int8)
        changed = float(np.mean(before != after)) >= 0.004 or level_up
        self.visits[(digest(before), index)] += 1
        positive, negative = self.model.get(index, (0, 0))
        self.model[index] = (positive + int(changed), negative + int(not changed))
        if changed:
            self.stats['changed'] += 1
        if changed and reason == 'new_object_probe':
            self.active = index
            self.consecutive = 0
            self.stats['options_started'] += 1
        elif changed and reason == 'repeat_until_effect_stops':
            self.consecutive += 1
            if self.consecutive >= 12:
                self.active = None
                self.stats['option_caps'] += 1
        elif reason == 'repeat_until_effect_stops':
            self.active = None
            self.consecutive = 0
            self.stats['option_evidence_stops'] += 1
        if terminal or level_up:
            self.active = None
            self.consecutive = 0


class MyAgent(Agent):
    # A bounded run is necessary for Kaggle's nine-hour submission runtime.
    MAX_ACTIONS = 240

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.controller = EventRepeat(SEED)
        self.last_frame = None
        self.last_action = None
        self.last_reason = None
        self.last_progress = 0

    @property
    def name(self) -> str:
        return f'{super().name}.E075-event-repeat.{self.MAX_ACTIONS}'

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state is GameState.WIN

    def choose_action(self, frames: list[FrameData], latest_frame: FrameData) -> GameAction:
        state = latest_frame.state
        if state in (GameState.NOT_PLAYED, GameState.GAME_OVER):
            self.last_frame = None
            self.last_action = None
            self.last_reason = None
            self.controller.active = None
            self.controller.consecutive = 0
            return GameAction.RESET

        if not latest_frame.frame:
            # A transient, terminal empty frame should not trigger a non-reset action.
            self.controller.active = None
            return GameAction.RESET
        cur = np.asarray(latest_frame.frame[-1], dtype=np.int8)
        levels = int(latest_frame.levels_completed)
        if self.last_frame is not None and self.last_action is not None:
            self.controller.observe(self.last_frame, cur, self.last_action,
                                    self.last_reason, levels > self.last_progress)
        legal = ids_to_mask(latest_frame.available_actions)
        index, reason = self.controller.select(cur, legal)
        action_id = SIMPLE_IDS[index] if index < N_SIMPLE else 6
        action = GameAction.from_id(int(action_id))
        if index >= N_SIMPLE:
            k = index - N_SIMPLE
            action.set_data({'x': int(k % GRID), 'y': int(k // GRID)})
        action.reasoning = {'strategy': 'observation_only_event_repeat', 'reason': reason}
        self.last_frame = cur.copy()
        self.last_action = index
        self.last_reason = reason
        self.last_progress = levels
        return action
