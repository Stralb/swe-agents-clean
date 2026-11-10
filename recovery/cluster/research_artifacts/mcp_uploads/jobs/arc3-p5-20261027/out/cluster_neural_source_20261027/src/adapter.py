"""Environment adapter: action mapping, masks, reward/progress, boundaries, budget accounting.

The only module that touches the ARC SDK. Knows nothing about networks, history length or algorithms.

Action space (settled, Phase 1): 4102 = 6 simple (ACTION1-5, ACTION7) + 4096 clicks (ACTION6).
    index 0..5      -> SIMPLE_IDS[index]
    index 6 + y*64+x -> ACTION6 at column x, row y (origin top-left)
RESET is never a learner action; the adapter issues exactly one RESET after GAME_OVER.

Reward (plan 4.3): r = max(0, progress_next - high_water_before); the high-water mark is monotone over the run.
Budget B counts *scorer-rule* actions (Phase 1 evidence): every step is 1, every RESET except the run's first
is 1. Raw environment commands are logged separately.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

import numpy as np

GRID = 64
SIMPLE_IDS = (1, 2, 3, 4, 5, 7)
N_SIMPLE = len(SIMPLE_IDS)
CLICK_TYPE = N_SIMPLE            # action-type index of ACTION6
N_TYPES = N_SIMPLE + 1
N_CLICK = GRID * GRID
N_ACTIONS = N_SIMPLE + N_CLICK   # 4102
NO_ACTION = -1                   # sentinel for "no previous action" after a reset
TERMINAL_STATES = ("GAME_OVER", "WIN")


class InterfaceError(RuntimeError):
    """Unexpected SDK/framework response (e.g. empty frame list during active play)."""


class IllegalAction(ValueError):
    """Learner selected an action outside the current legal mask."""


# ---------------------------------------------------------------- action mapping and masks
def index_to_action(idx: int) -> tuple[int, Optional[tuple[int, int]]]:
    """Action index -> (ARC action id, (x, y) or None)."""
    if 0 <= idx < N_SIMPLE:
        return SIMPLE_IDS[idx], None
    if N_SIMPLE <= idx < N_ACTIONS:
        k = idx - N_SIMPLE
        return 6, (k % GRID, k // GRID)
    raise ValueError(f"action index out of range: {idx}")


def action_to_index(action_id: int, xy: Optional[tuple[int, int]] = None) -> int:
    if action_id == 6:
        x, y = xy
        if not (0 <= x < GRID and 0 <= y < GRID):
            raise ValueError(f"click out of range: {xy}")
        return N_SIMPLE + y * GRID + x
    return SIMPLE_IDS.index(action_id)


def action_type(idx: int) -> int:
    return idx if idx < N_SIMPLE else CLICK_TYPE


def build_mask(available: Iterable[int]) -> np.ndarray:
    """Legal-action mask from `available_actions`. All 4096 clicks are legal whenever ACTION6 is."""
    av = set(int(a) for a in available)
    m = np.zeros(N_ACTIONS, dtype=bool)
    for i, aid in enumerate(SIMPLE_IDS):
        m[i] = aid in av
    m[N_SIMPLE:] = 6 in av
    return m


def type_mask(mask: np.ndarray) -> np.ndarray:
    """bool[N_TYPES]: which action types are legal (click is one type)."""
    return np.concatenate([mask[:N_SIMPLE], [mask[N_SIMPLE:].any()]])


def sample_type_uniform(rng: np.random.Generator, mask: np.ndarray) -> int:
    """Uniform over legal action types; if ACTION6, a uniform legal location (type-balanced exploration)."""
    tm = np.flatnonzero(type_mask(mask))
    if len(tm) == 0:
        raise IllegalAction("no legal action types")
    t = int(rng.choice(tm))
    if t < N_SIMPLE:
        return t
    legal = np.flatnonzero(mask[N_SIMPLE:])
    return N_SIMPLE + int(rng.choice(legal))


def sample_flat_uniform(rng: np.random.Generator, mask: np.ndarray) -> int:
    """Uniform over every legal index (clicks dominate whenever ACTION6 is legal)."""
    legal = np.flatnonzero(mask)
    if len(legal) == 0:
        raise IllegalAction("no legal actions")
    return int(rng.choice(legal))


# ---------------------------------------------------------------- data contracts
@dataclass
class RawFrame:
    """SDK/framework-neutral response to one command."""
    frames: list                 # list of 64x64 arrays; empty only for steps sent during GAME_OVER
    state: str                   # NOT_PLAYED | NOT_FINISHED | WIN | GAME_OVER
    levels_completed: int
    win_levels: int
    available_actions: list


def raw_from_sdk(r) -> RawFrame:
    return RawFrame(list(r.frame), r.state.value, int(r.levels_completed), int(r.win_levels),
                    [int(a) for a in r.available_actions])


def raw_from_framework(fd) -> RawFrame:
    """ARC-AGI-3-Agents FrameData (frames are nested lists) -> RawFrame."""
    return RawFrame([np.asarray(f, dtype=np.int8) for f in fd.frame], fd.state.value,
                    int(fd.levels_completed), int(fd.win_levels), [int(a) for a in fd.available_actions])


@dataclass
class Observation:
    """Canonical observation. Representations decide how much of it they use (V0 uses frame + prev_frame)."""
    frame: np.ndarray            # int8[64,64]: last frame of the step's frame list
    prev_frame: np.ndarray       # int8[64,64]: last frame of the previous step (== frame right after a reset)
    mask: np.ndarray             # bool[N_ACTIONS]
    prev_action: int             # NO_ACTION right after a reset
    progress: int                # levels_completed reported now
    high_water: int              # max progress reached so far in this run (never reset)
    win_levels: int


@dataclass
class Transition:
    obs: Observation
    action: int
    reward: float
    next_obs: Observation        # for terminal transitions this is the terminal frame, NOT the post-reset frame
    terminal: bool               # GAME_OVER or WIN: never bootstrap
    truncated: bool              # budget exhausted: non-terminal, may bootstrap from next_obs
    info: dict = field(default_factory=dict)


class Tracker:
    """Reward / high-water / mask / budget bookkeeping. Pure Python: shared by ArcSession, the synthetic tasks
    and the Kaggle framework bridge so all three have identical semantics."""

    def __init__(self, budget: Optional[int], free_first_reset: bool = True):
        self.budget = budget
        self.free_first_reset = free_first_reset   # True for direct SDK use; framework RESETs may all be counted
        self.actions = 0             # scorer-rule actions
        self.env_commands = 0        # steps + resets actually sent
        self.resets = 0
        self.high_water = 0
        self.episode = -1
        self.obs: Optional[Observation] = None
        self._last_mask: Optional[np.ndarray] = None

    @property
    def exhausted(self) -> bool:
        return self.budget is not None and self.actions >= self.budget

    def note_reset_command(self) -> None:
        """Call when a RESET is sent. Direct SDK use: the first reset is free under the scorer's rule."""
        self.env_commands += 1
        if self.resets > 0 or not self.free_first_reset:
            self.actions += 1
        self.resets += 1

    def _mask(self, raw: RawFrame) -> np.ndarray:
        if raw.available_actions:
            self._last_mask = build_mask(raw.available_actions)
        elif self._last_mask is None:
            raise InterfaceError("no available_actions and no earlier mask")
        return self._last_mask       # empty available_actions: reuse the last non-empty mask (plan 3.3)

    @staticmethod
    def _frame(raw: RawFrame) -> np.ndarray:
        if not raw.frames:
            raise InterfaceError("empty frame list during active play")
        f = np.asarray(raw.frames[-1], dtype=np.int8)
        if f.shape != (GRID, GRID):
            raise InterfaceError(f"unexpected frame shape {f.shape}")
        return f

    def begin_episode(self, raw: RawFrame) -> Observation:
        """First observation after any reset: previous frame = new frame, previous action = sentinel."""
        frame = self._frame(raw)
        self.high_water = max(self.high_water, raw.levels_completed)
        self.episode += 1
        self.obs = Observation(frame, frame, self._mask(raw), NO_ACTION, raw.levels_completed,
                               self.high_water, raw.win_levels)
        return self.obs

    def advance(self, action: int, raw: RawFrame) -> Transition:
        assert self.obs is not None, "begin_episode() first"
        self.env_commands += 1
        self.actions += 1
        frame = self._frame(raw)
        before = self.high_water
        reward = float(max(0, raw.levels_completed - before))
        self.high_water = max(before, raw.levels_completed)
        terminal = raw.state in TERMINAL_STATES
        nxt = Observation(frame, self.obs.frame, self._mask(raw), action, raw.levels_completed,
                          self.high_water, raw.win_levels)
        t = Transition(self.obs, action, reward, nxt, terminal, (not terminal) and self.exhausted,
                       {"state": raw.state, "level_up": reward > 0,
                        "frame_changed": not np.array_equal(frame, self.obs.frame),
                        "episode": self.episode})
        self.obs = nxt
        return t


# ---------------------------------------------------------------- sessions
class BaseSession:
    """One run = one environment session. Subclasses implement _open/_send/_reset."""

    def __init__(self):
        self.tracker: Optional[Tracker] = None
        self.status = "idle"         # running | won | budget | error

    # --- to implement
    def _open(self, game: str, env_seed: int) -> None: ...
    def _send(self, action_id: int, xy: Optional[tuple[int, int]]) -> RawFrame: ...
    def _reset(self) -> RawFrame: ...
    def scorecard(self) -> Optional[dict]: return None

    # --- shared
    @property
    def obs(self) -> Observation:
        return self.tracker.obs

    @property
    def done(self) -> bool:
        return self.status != "running"

    def start_run(self, game: str, budget: int, env_seed: int = 0) -> Observation:
        self.tracker = Tracker(budget)
        self._open(game, env_seed)
        self.status = "running"
        self.tracker.note_reset_command()          # first reset: free
        return self.tracker.begin_episode(self._reset())

    def step(self, idx: int) -> Transition:
        if self.done:
            raise RuntimeError(f"session is {self.status}")
        if not (0 <= idx < N_ACTIONS) or not self.obs.mask[idx]:
            raise IllegalAction(f"action {idx} is not legal")
        aid, xy = index_to_action(idx)
        t = self.tracker.advance(idx, self._send(aid, xy))
        if t.info["state"] == "WIN":
            self.status = "won"                    # plan 4.4: stop at WIN
        elif self.tracker.exhausted:
            self.status = "budget"                 # never issue a reset after exhaustion
        elif t.terminal:                           # GAME_OVER: exactly one RESET, then a fresh episode
            self.tracker.note_reset_command()
            self.tracker.begin_episode(self._reset())
            if self.tracker.exhausted:
                self.status = "budget"
        return t


class ArcSession(BaseSession):
    """Real SDK session (NORMAL mode: games run locally; scored by the SDK's official scorecard)."""

    def __init__(self, arc=None):
        super().__init__()
        import arc_agi
        from arc_agi import OperationMode
        self.arc = arc or arc_agi.Arcade(operation_mode=OperationMode.NORMAL)
        self.env = None
        self.card_id = None

    def _open(self, game: str, env_seed: int) -> None:
        self.card_id = self.arc.open_scorecard()
        self.env = self.arc.make(game, seed=env_seed, scorecard_id=self.card_id)
        if self.env is None:
            raise InterfaceError(f"could not create environment {game!r}")

    def _send(self, action_id: int, xy) -> RawFrame:
        from arcengine import GameAction
        ga = GameAction.from_id(action_id)
        r = self.env.step(ga, data={"x": int(xy[0]), "y": int(xy[1])}) if xy else self.env.step(ga)
        return raw_from_sdk(r)

    def _reset(self) -> RawFrame:
        return raw_from_sdk(self.env.reset())

    def scorecard(self) -> Optional[dict]:
        import json
        card = self.arc.get_scorecard(self.card_id)
        return json.loads(card.model_dump_json()) if card is not None else None
