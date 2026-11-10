"""Double DQN (van Hasselt et al. 2016; DQN: Mnih et al. 2015) over the flat 4102-action space.

Type-balanced epsilon exploration (plan 5.3): on an epsilon step pick a uniform legal action *type* (ACTION6 is one
type) then a uniform legal location; on a greedy step take the highest legal Q over the full action space.
Replay is ordinary arrays (plan 5.4); all four frames of a transition are stored, so memory is measured, not assumed.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

from .adapter import GRID, N_ACTIONS, N_SIMPLE, N_TYPES, Observation, Transition, sample_type_uniform, type_mask
from .model import ObsBatch, QNet, collate, model_info

NEG = -1e9   # finite mask value: keeps every intermediate finite (no 0 * -inf)


class ObsStore:
    """Struct-of-arrays store of Observations. Legal mask kept as per-type bools (clicks are all-or-nothing)."""

    def __init__(self, cap: int):
        self.frame = np.zeros((cap, GRID, GRID), np.int8)
        self.prev_frame = np.zeros((cap, GRID, GRID), np.int8)
        self.prev_action = np.zeros(cap, np.int16)
        self.progress = np.zeros((cap, 2), np.float32)
        self.tmask = np.zeros((cap, N_TYPES), bool)

    def put(self, i: int, o: Observation) -> None:
        self.frame[i], self.prev_frame[i], self.prev_action[i] = o.frame, o.prev_frame, o.prev_action
        self.progress[i] = (o.progress, o.high_water)
        self.tmask[i] = type_mask(o.mask)

    def get(self, idx: np.ndarray) -> ObsBatch:
        tm = self.tmask[idx]
        mask = np.zeros((len(idx), N_ACTIONS), bool)
        mask[:, :N_SIMPLE] = tm[:, :N_SIMPLE]
        mask[:, N_SIMPLE:] = tm[:, N_SIMPLE:N_SIMPLE + 1]
        return ObsBatch(torch.from_numpy(self.frame[idx]).long(), torch.from_numpy(self.prev_frame[idx]).long(),
                        torch.from_numpy(self.prev_action[idx].astype(np.int64)),
                        torch.from_numpy(self.progress[idx]), torch.from_numpy(mask))

    @property
    def nbytes(self) -> int:
        return sum(a.nbytes for a in (self.frame, self.prev_frame, self.prev_action, self.progress, self.tmask))


class DQN:
    name = "dqn"

    def __init__(self, arch: dict, params: dict, updates_disabled: bool = False):
        self.arch, self.p, self.updates_disabled = arch, params, updates_disabled

    # ---------------------------------------------------------------- lifecycle
    def start_run(self, seed: int) -> None:
        torch.manual_seed(seed)
        self.rng = np.random.default_rng(seed)
        self.net, self.target = QNet(self.arch), QNet(self.arch)
        self.target.load_state_dict(self.net.state_dict())
        for prm in self.target.parameters():
            prm.requires_grad_(False)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.p["lr"])
        cap = self.p["replay_capacity"]
        self.store, self.next_store = ObsStore(cap), ObsStore(cap)
        self.action = np.zeros(cap, np.int16)
        self.reward = np.zeros(cap, np.float32)
        self.done = np.zeros(cap, bool)
        self.size = self.ptr = 0
        self.n_act = self.n_seen = self.grad_steps = self.target_syncs = 0
        self.loss_ema = self.q_ema = None

    def epsilon(self) -> float:
        p = self.p
        frac = min(1.0, self.n_act / max(1, p["eps_decay_actions"]))
        return p["eps_start"] + (p["eps_end"] - p["eps_start"]) * frac

    def act(self, obs: Observation) -> int:
        eps = self.epsilon()
        self.n_act += 1
        if self.rng.random() < eps:
            return sample_type_uniform(self.rng, obs.mask)          # type-balanced epsilon exploration
        with torch.no_grad():
            q = self.net(collate([obs]))[0].masked_fill(~torch.from_numpy(obs.mask), NEG)
        return int(q.argmax())

    def observe(self, t: Transition) -> None:
        i = self.ptr
        self.store.put(i, t.obs)
        self.next_store.put(i, t.next_obs)
        self.action[i], self.reward[i], self.done[i] = t.action, t.reward, t.terminal
        self.ptr = (i + 1) % self.p["replay_capacity"]
        self.size = min(self.size + 1, self.p["replay_capacity"])
        self.n_seen += 1
        if self.updates_disabled:
            return
        if self.n_seen >= self.p["warmup"] and self.n_seen % self.p["train_every"] == 0:
            self._train()
        if self.n_seen % self.p["target_update"] == 0:
            self.target.load_state_dict(self.net.state_dict())
            self.target_syncs += 1

    def finish(self, final_obs: Optional[Observation]) -> None: ...

    # ---------------------------------------------------------------- learning
    def _train(self) -> None:
        p = self.p
        idx = self.rng.integers(0, self.size, p["batch"])
        b, nb = self.store.get(idx), self.next_store.get(idx)
        a = torch.from_numpy(self.action[idx].astype(np.int64))
        r, d = torch.from_numpy(self.reward[idx]), torch.from_numpy(self.done[idx])
        q = self.net(b).gather(1, a[:, None]).squeeze(1)
        with torch.no_grad():
            qt = self.target(nb)
            if p["double"]:                                        # online net selects (masked), target evaluates
                a2 = self.net(nb).masked_fill(~nb.mask, NEG).argmax(1)
                nxt = qt.gather(1, a2[:, None]).squeeze(1)
            else:
                nxt = qt.masked_fill(~nb.mask, NEG).max(1).values
            nxt = torch.where(nb.mask.any(1), nxt, torch.zeros_like(nxt))
            y = torch.where(d, r, r + p["gamma"] * nxt)            # terminal: no bootstrap, never 0 * -inf
        loss = F.huber_loss(q, y, delta=p["huber_delta"])
        self.opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.net.parameters(), p["grad_clip"])
        self.opt.step()
        self.grad_steps += 1
        lv, qv = float(loss.detach()), float(q.detach().mean())
        self.loss_ema = lv if self.loss_ema is None else 0.99 * self.loss_ema + 0.01 * lv
        self.q_ema = qv if self.q_ema is None else 0.99 * self.q_ema + 0.01 * qv

    # ---------------------------------------------------------------- reporting / checkpointing
    def diagnostics(self) -> dict:
        return {"algo": "dqn", "actions_seen": self.n_seen, "gradient_steps": self.grad_steps,
                "target_syncs": self.target_syncs, "epsilon": self.epsilon(), "loss_ema": self.loss_ema,
                "q_mean_ema": self.q_ema, "replay_size": self.size, "updates_disabled": self.updates_disabled,
                "replay_mb": round((self.store.nbytes + self.next_store.nbytes) / 2**20, 1)}

    def model_info(self) -> dict:
        return model_info(self.net, self.arch)

    def state_dict(self) -> dict:
        return {"net": self.net.state_dict(), "target": self.target.state_dict(), "opt": self.opt.state_dict(),
                "counters": {"n_act": self.n_act, "n_seen": self.n_seen, "grad_steps": self.grad_steps,
                          "target_syncs": self.target_syncs}, "rng": self.rng.bit_generator.state}

    def load_state_dict(self, d: dict) -> None:
        self.net.load_state_dict(d["net"])
        self.target.load_state_dict(d["target"])
        self.opt.load_state_dict(d["opt"])
        for k, v in d["counters"].items():
            setattr(self, k, v)
        self.rng.bit_generator.state = d["rng"]

