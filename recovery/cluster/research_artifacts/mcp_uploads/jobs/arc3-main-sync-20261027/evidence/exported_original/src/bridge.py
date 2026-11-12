"""Kaggle / ARC-AGI-3-Agents framework bridge (plan 4.2: 'deliver the previous action's outcome before the next act').

The framework calls  choose_action(frames, latest_frame) -> GameAction  and offers no observe hook. This bridge turns
that call pattern into the learner contract:

    call n : latest_frame = outcome of the action chosen at call n-1
             -> Tracker.advance(...) builds the Transition -> learner.observe(t) -> learner.act(obs)

It reuses adapter.Tracker, so reward, high-water and masks are identical to ArcSession. Exactly one RESET follows a
GAME_OVER (never two in a row); the learner never selects RESET. The budget is enforced by the framework loop
(`MAX_ACTIONS`), so the tracker runs unbounded here; the outcome of the very last action is never observed.
"""
from __future__ import annotations

from typing import Optional

from .adapter import RawFrame, Tracker, index_to_action, raw_from_framework
from .learner import Learner

RESET, ACT = "reset", "act"


class FrameworkBridge:
    def __init__(self, learner: Learner, seed: int = 0):
        self.learner = learner
        self.tracker = Tracker(budget=None, free_first_reset=False)   # framework RESETs are ordinary counted commands
        self.pending: Optional[int] = None       # action awaiting its outcome
        self.awaiting_reset = False              # last command was our RESET; latest frame is its result
        self.n_observed = 0
        learner.start_run(seed)

    def choose(self, latest) -> tuple:
        """Return ('act', action_index) or ('reset', None). `latest` is a framework FrameData or a RawFrame."""
        raw: RawFrame = latest if isinstance(latest, RawFrame) else raw_from_framework(latest)
        tk = self.tracker
        if self.awaiting_reset:                                   # result of our RESET: start a fresh episode
            self.awaiting_reset = False
            tk.begin_episode(raw)
        elif self.pending is not None:                            # outcome of the previous learner action
            t = tk.advance(self.pending, raw)
            self.pending = None
            self.learner.observe(t)
            self.n_observed += 1
            if t.terminal and t.info["state"] == "GAME_OVER":
                return self._reset()
        elif tk.obs is None:                                      # first call of the run
            if raw.state in ("NOT_PLAYED", "GAME_OVER"):
                return self._reset()
            tk.begin_episode(raw)
        idx = self.learner.act(tk.obs)
        self.pending = idx
        return ACT, idx

    def _reset(self) -> tuple:
        self.tracker.note_reset_command()
        self.awaiting_reset = True
        return RESET, None

    def finish(self) -> None:
        self.learner.finish(self.tracker.obs)


def to_game_action(idx: int):
    """Action index -> framework GameAction with click data attached (ACTION6 needs {'x','y'})."""
    from arcengine import GameAction
    aid, xy = index_to_action(idx)
    ga = GameAction.from_id(aid)
    if xy is not None:
        ga.set_data({"x": xy[0], "y": xy[1]})
    return ga
