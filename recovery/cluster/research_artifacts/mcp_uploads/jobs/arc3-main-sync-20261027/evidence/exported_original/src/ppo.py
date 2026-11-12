"""PPO (Schulman et al. 2017) with GAE (Schulman et al. 2016): one live environment, sequential rollouts.

Provisional V0 policy factorisation (plan 5.3):
    log p(a) = log p(type) [+ log p(location | ACTION6) for clicks]
    entropy  = H(type) + p(ACTION6) * H(location | ACTION6)
Masks stored at collection time are reused in the update (they live in the stored Observation).
GAE never propagates across a terminal boundary; a rollout cutoff bootstraps from the last valid observation.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.distributions import Categorical

from .adapter import N_SIMPLE, CLICK_TYPE, Observation, Transition, type_mask
from .model import ActorCritic, ObsBatch, collate, model_info

NEG = -1e9


def evaluate_actions(net: ActorCritic, b: ObsBatch, actions: torch.Tensor):
    """Joint log-prob, entropy and value for stored actions under the current policy (shared by act and update)."""
    tl, cl, v = net(b)
    tm = torch.cat([b.mask[:, :N_SIMPLE], b.mask[:, N_SIMPLE:].any(1, keepdim=True)], 1)
    lp_t = F.log_softmax(tl.masked_fill(~tm, NEG), 1)
    p_t = lp_t.exp()
    lp_c = F.log_softmax(cl.masked_fill(~b.mask[:, N_SIMPLE:], NEG), 1)
    p_c = lp_c.exp()
    is_click = actions >= N_SIMPLE
    typ = torch.where(is_click, torch.full_like(actions, CLICK_TYPE), actions)
    loc = (actions - N_SIMPLE).clamp(min=0)
    logp = lp_t.gather(1, typ[:, None]).squeeze(1)
    logp = logp + torch.where(is_click, lp_c.gather(1, loc[:, None]).squeeze(1), torch.zeros_like(logp))
    ent = -(p_t * lp_t).sum(1) + p_t[:, CLICK_TYPE] * -(p_c * lp_c).sum(1)
    return logp, ent, v


class PPO:
    name = "ppo"

    def __init__(self, arch: dict, params: dict, updates_disabled: bool = False):
        self.arch, self.p, self.updates_disabled = arch, params, updates_disabled

    def start_run(self, seed: int) -> None:
        torch.manual_seed(seed)
        self.net = ActorCritic(self.arch)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=self.p["lr"], eps=1e-5)
        self.buf: list = []
        self._pending = None
        self.n_act = self.rollout_updates = self.grad_steps = self.partial_rollouts = 0
        self.ema: dict = {}

    # ---------------------------------------------------------------- acting
    def act(self, obs: Observation) -> int:
        self.n_act += 1
        with torch.no_grad():
            tl, cl, v = self.net(collate([obs]))
            tm = torch.from_numpy(type_mask(obs.mask))
            lp_t = F.log_softmax(tl[0].masked_fill(~tm, NEG), 0)
            typ = int(Categorical(logits=lp_t).sample())
            if typ < N_SIMPLE:
                idx, lp = typ, lp_t[typ]
            else:
                lp_c = F.log_softmax(cl[0].masked_fill(~torch.from_numpy(obs.mask[N_SIMPLE:]), NEG), 0)
                loc = int(Categorical(logits=lp_c).sample())
                idx, lp = N_SIMPLE + loc, lp_t[CLICK_TYPE] + lp_c[loc]
        self._pending = (obs, idx, float(lp), float(v[0]))
        return idx

    def observe(self, t: Transition) -> None:
        obs, idx, lp, v = self._pending
        assert t.action == idx, "observe() must follow the matching act()"
        self.buf.append((obs, idx, lp, v, t.reward, t.terminal))
        if len(self.buf) >= self.p["rollout"]:
            self._end_rollout(0.0 if t.terminal else self._value(t.next_obs))

    def finish(self, final_obs: Optional[Observation]) -> None:
        """Process a partial final rollout safely (bootstrap only if its last transition was non-terminal)."""
        if not self.buf:
            return
        self.partial_rollouts += 1
        if len(self.buf) < self.p["minibatches"]:
            self.buf.clear()
            return
        last_terminal = self.buf[-1][5]
        self._end_rollout(0.0 if (last_terminal or final_obs is None) else self._value(final_obs))

    def _value(self, obs: Observation) -> float:
        with torch.no_grad():
            return float(self.net(collate([obs]))[2][0])

    # ---------------------------------------------------------------- learning
    def _end_rollout(self, last_value: float) -> None:
        buf, self.buf = self.buf, []
        if self.updates_disabled:
            return
        p = self.p
        obs = [b[0] for b in buf]
        actions = torch.tensor([b[1] for b in buf], dtype=torch.long)
        old_lp = torch.tensor([b[2] for b in buf], dtype=torch.float32)
        values = np.array([b[3] for b in buf], dtype=np.float32)
        rewards = np.array([b[4] for b in buf], dtype=np.float32)
        dones = np.array([b[5] for b in buf], dtype=np.float32)
        adv = compute_gae(rewards, values, dones, last_value, p["gamma"], p["gae_lambda"])
        ret = torch.from_numpy(adv + values)
        adv = torch.from_numpy(adv)
        n = len(buf)
        mb = int(np.ceil(n / p["minibatches"]))
        for _ in range(p["epochs"]):
            perm = torch.randperm(n)
            for chunk in perm.split(mb):
                ci = chunk.tolist()
                logp, ent, v = evaluate_actions(self.net, collate([obs[i] for i in ci]), actions[chunk])
                a = adv[chunk]
                if len(ci) > 1:
                    a = (a - a.mean()) / (a.std() + 1e-8)
                ratio = (logp - old_lp[chunk]).exp()
                pg = -torch.min(ratio * a, ratio.clamp(1 - p["clip"], 1 + p["clip"]) * a).mean()
                vf = 0.5 * ((v - ret[chunk]) ** 2).mean()
                loss = pg + p["vf_coef"] * vf - p["ent_coef"] * ent.mean()
                self.opt.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), p["grad_clip"])
                self.opt.step()
                self.grad_steps += 1
                self._ema(loss=float(loss.detach()), pg=float(pg.detach()), vf=float(vf.detach()), entropy=float(ent.detach().mean()),
                          kl=float((old_lp[chunk] - logp.detach()).mean()),
                          clipfrac=float(((ratio - 1).abs() > p["clip"]).float().mean()))
        self.rollout_updates += 1

    def _ema(self, **kw) -> None:
        for k, v in kw.items():
            self.ema[k] = v if k not in self.ema else 0.98 * self.ema[k] + 0.02 * v

    # ---------------------------------------------------------------- reporting / checkpointing
    def diagnostics(self) -> dict:
        return {"algo": "ppo", "actions_seen": self.n_act, "rollout_update_events": self.rollout_updates,
                "gradient_steps": self.grad_steps, "partial_rollouts": self.partial_rollouts,
                "updates_disabled": self.updates_disabled, **{f"{k}_ema": v for k, v in self.ema.items()}}

    def model_info(self) -> dict:
        return model_info(self.net, self.arch)

    def state_dict(self) -> dict:
        return {"net": self.net.state_dict(), "opt": self.opt.state_dict(),
                "counters": {"n_act": self.n_act, "rollout_updates": self.rollout_updates,
                          "grad_steps": self.grad_steps, "partial_rollouts": self.partial_rollouts}}

    def load_state_dict(self, d: dict) -> None:
        self.net.load_state_dict(d["net"])
        self.opt.load_state_dict(d["opt"])
        for k, v in d["counters"].items():
            setattr(self, k, v)


def compute_gae(rewards, values, dones, last_value, gamma, lam) -> np.ndarray:
    """GAE that never crosses a terminal boundary: done[t] cuts both the bootstrap and the trace."""
    n = len(rewards)
    adv = np.zeros(n, dtype=np.float32)
    gae = 0.0
    for t in reversed(range(n)):
        nxt = last_value if t == n - 1 else values[t + 1]
        nonterm = 1.0 - dones[t]
        delta = rewards[t] + gamma * nxt * nonterm - values[t]
        gae = delta + gamma * lam * nonterm * gae
        adv[t] = gae
    return adv
