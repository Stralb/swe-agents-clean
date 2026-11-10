from __future__ import annotations

import copy
import math
import random
import time
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn

from .action_bank import ActionBank, ActionKey
from .qnet import ActionValueNetwork, QNetConfig, c51_project
from .replay import NStepAccumulator, ReplayBuffer, StepTransition


@dataclass
class AgentStats:
    updates: int = 0
    gradient_steps: int = 0
    loss_sum: float = 0.0
    td_sum: float = 0.0
    q_sum: float = 0.0
    grad_norm_sum: float = 0.0
    train_seconds: float = 0.0
    act_seconds: float = 0.0
    epsilon_actions: int = 0
    greedy_actions: int = 0
    epsilon_uniform_actions: int = 0
    epsilon_typeprior_actions: int = 0
    epsilon_structured_actions: int = 0


class DQNAgent:
    def __init__(self, state_dim: int, system: dict, cfg: dict, seed: int, device: torch.device):
        self.system = copy.deepcopy(system)
        self.cfg = cfg
        self.tcfg = cfg["training"]
        self.device = device
        # Keep behavior-policy RNG separate from replay/training RNG so an
        # updates-disabled control sees the same epsilon/random action stream
        # until learned values themselves cause policy divergence.
        # Separate RNG streams keep epsilon/greedy decisions matched across
        # exploration treatments even when structured selectors consume different
        # amounts of randomness.
        self.epsilon_rng = random.Random(int(seed))
        self.explore_rng = random.Random(int(seed) + 3571)
        self.replay_rng = random.Random(int(seed) + 7919)
        torch.manual_seed(int(seed))
        self.bank = ActionBank(cfg["click_action_id"], cfg["click_size"], max_action_id=int(cfg.get("max_action_id", 7)))
        qcfg = QNetConfig(
            state_dim=state_dim,
            action_dim=self.bank.action_dim,
            hidden_dim=int(self.tcfg["hidden_dim"]),
            dueling=bool(system.get("dueling", False)),
            distributional=bool(system.get("distributional", False)),
            atoms=int(self.tcfg["c51_atoms"]),
            vmin=float(self.tcfg["c51_vmin"]),
            vmax=float(self.tcfg["c51_vmax"]),
        )
        self.online = ActionValueNetwork(qcfg).to(device)
        self.target = ActionValueNetwork(qcfg).to(device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.initial = {k: v.detach().cpu().clone() for k, v in self.online.state_dict().items()}
        self.optimizer = torch.optim.Adam(self.online.parameters(), lr=float(self.tcfg["learning_rate"]))
        self.replay = ReplayBuffer(
            int(self.tcfg["replay_capacity"]),
            prioritized=bool(system.get("per", False)),
            alpha=float(self.tcfg["per_alpha"]),
            eps=float(self.tcfg["per_eps"]),
        )
        self.nstep = NStepAccumulator(int(system.get("n_step", 1)), float(self.tcfg["gamma"]))
        self.stats = AgentStats()
        self.action_count = 0

    @property
    def learns(self) -> bool:
        return bool(self.system.get("learn", True))

    def epsilon(self) -> float:
        start = float(self.tcfg["epsilon_start"])
        end = float(self.tcfg["epsilon_end"])
        horizon = max(1, int(self.tcfg["epsilon_decay_actions"]))
        f = min(1.0, self.action_count / horizon)
        return start + f * (end - start)

    def beta(self) -> float:
        start = float(self.tcfg["per_beta_start"])
        end = float(self.tcfg["per_beta_end"])
        horizon = max(1, int(self.tcfg["epsilon_decay_actions"]))
        f = min(1.0, self.action_count / horizon)
        return start + f * (end - start)

    def _to(self, x: np.ndarray) -> torch.Tensor:
        return torch.as_tensor(x, dtype=torch.float32, device=self.device)

    def q_values(self, state: np.ndarray, available: list[int] | tuple[int, ...], target: bool = False):
        keys, acts = self.bank.encode_candidates(available)
        if not keys:
            return keys, torch.empty(0, device=self.device)
        net = self.target if target else self.online
        with torch.no_grad():
            q = net.q_values(self._to(state), self._to(acts))
        return keys, q

    def random_uniform_action(self, available: list[int], rng: random.Random | None = None) -> ActionKey:
        rng = self.explore_rng if rng is None else rng
        aid = rng.choice(list(available))
        if int(aid) == self.bank.click_action_id:
            return ActionKey(int(aid), rng.randrange(self.bank.click_size), rng.randrange(self.bank.click_size))
        return ActionKey(int(aid))

    def act(self, state: np.ndarray, available: list[int], explore_fn=None) -> tuple[ActionKey, str]:
        t0 = time.perf_counter()
        if not available:
            raise ValueError("No legal actions")
        eps = self.epsilon()
        if self.epsilon_rng.random() < eps:
            if explore_fn is None:
                a, label = self.random_uniform_action(available), "uniform"
            else:
                a, label = explore_fn(self.explore_rng, self.action_count)
                if not isinstance(a, ActionKey):
                    raise TypeError(f"explore_fn must return ActionKey, got {type(a)!r}")
                if int(a.action_id) not in {int(x) for x in available}:
                    raise AssertionError(("illegal_exploration_action", a, available, label))
            self.stats.epsilon_actions += 1
            if label == "d14":
                self.stats.epsilon_structured_actions += 1
            elif label == "type_prior":
                self.stats.epsilon_typeprior_actions += 1
            else:
                self.stats.epsilon_uniform_actions += 1
        else:
            keys, q = self.q_values(state, available, target=False)
            a = keys[int(torch.argmax(q).item())]
            label = "greedy"
            self.stats.greedy_actions += 1
        self.action_count += 1
        self.stats.act_seconds += time.perf_counter() - t0
        return a, label

    def observe(
        self,
        state: np.ndarray,
        current_available: tuple[int, ...],
        action: ActionKey,
        reward: float,
        next_state: np.ndarray,
        next_available: tuple[int, ...],
        terminal: bool,
    ) -> None:
        step = StepTransition(
            state=np.asarray(state, dtype=np.float32).copy(),
            available=tuple(int(x) for x in current_available),
            action=self.bank.encode(action),
            action_key=(int(action.action_id), int(action.x), int(action.y)),
            reward=float(reward),
            next_state=np.asarray(next_state, dtype=np.float32).copy(),
            next_available=tuple(int(x) for x in next_available),
            terminal=bool(terminal),
        )
        for t in self.nstep.append(step):
            self.replay.add(t)
        if not self.learns:
            return
        if self.action_count < int(self.tcfg["warmup_actions"]):
            return
        if self.action_count % int(self.tcfg["train_every_actions"]) != 0:
            return
        if len(self.replay) < int(self.tcfg["batch_size"]):
            return
        self._train_step()
        if self.action_count % int(self.tcfg["target_update_actions"]) == 0:
            self.target.load_state_dict(self.online.state_dict())

    def finish(self) -> None:
        for t in self.nstep.flush():
            self.replay.add(t)


    def _chosen_index(self, keys, action_key: tuple[int, int, int]) -> int:
        aid, x, y = action_key
        for i, k in enumerate(keys):
            if (int(k.action_id), int(k.x), int(k.y)) == (aid, x, y):
                return i
        raise KeyError((action_key, keys[:8], len(keys)))

    def _current_scalar_q(self, t) -> torch.Tensor:
        keys, acts_np = self.bank.encode_candidates(t.available)
        if not keys:
            raise ValueError("Replay transition has no current legal actions")
        idx = self._chosen_index(keys, t.action_key)
        return self.online.q_values(self._to(t.state), self._to(acts_np))[idx]

    def _current_logits(self, t) -> torch.Tensor:
        keys, acts_np = self.bank.encode_candidates(t.available)
        if not keys:
            raise ValueError("Replay transition has no current legal actions")
        idx = self._chosen_index(keys, t.action_key)
        return self.online.logits(self._to(t.state), self._to(acts_np))[idx]

    def _next_value_scalar(self, t) -> torch.Tensor:
        if t.terminal or not t.next_available:
            return torch.tensor(0.0, device=self.device)
        keys, acts_np = self.bank.encode_candidates(t.next_available)
        acts = self._to(acts_np)
        state = self._to(t.next_state)
        with torch.no_grad():
            online_q = self.online.q_values(state, acts)
            best = int(torch.argmax(online_q).item())
            target_q = self.target.q_values(state, acts)[best]
        return target_q

    def _next_distribution(self, t) -> torch.Tensor:
        atoms = int(self.tcfg["c51_atoms"])
        if t.terminal or not t.next_available:
            # This distribution is multiplied by zero bootstrap in projection;
            # keeping a valid probability vector avoids NaNs.
            return torch.full((atoms,), 1.0 / atoms, device=self.device)
        _, acts_np = self.bank.encode_candidates(t.next_available)
        acts = self._to(acts_np)
        state = self._to(t.next_state)
        with torch.no_grad():
            best = int(torch.argmax(self.online.q_values(state, acts)).item())
            logits = self.target.logits(state, acts)[best]
            return torch.softmax(logits, dim=-1)

    def _train_step(self) -> None:
        t0 = time.perf_counter()
        batch_size = int(self.tcfg["batch_size"])
        idx, batch, weights_np = self.replay.sample(batch_size, self.beta(), self.replay_rng)
        weights = self._to(weights_np)
        self.optimizer.zero_grad(set_to_none=True)
        td_for_priority = []

        if bool(self.system.get("distributional", False)):
            next_probs = torch.stack([self._next_distribution(t) for t in batch])
            reward = torch.tensor([t.reward for t in batch], dtype=torch.float32, device=self.device)
            terminal = torch.tensor([float(t.terminal) for t in batch], dtype=torch.float32, device=self.device)
            gamma_n = torch.tensor([t.gamma_n for t in batch], dtype=torch.float32, device=self.device)
            target_dist = c51_project(
                next_probs,
                reward,
                terminal,
                gamma_n,
                self.online.support,
                float(self.tcfg["c51_vmin"]),
                float(self.tcfg["c51_vmax"]),
            )
            losses = []
            q_obs = []
            q_tgt = []
            for i, t in enumerate(batch):
                logits = self._current_logits(t)
                logp = torch.log_softmax(logits, dim=-1)
                losses.append(-(target_dist[i] * logp).sum())
                p = torch.softmax(logits.detach(), dim=-1)
                q_obs.append((p * self.online.support).sum())
                q_tgt.append((target_dist[i] * self.online.support).sum())
            loss_vec = torch.stack(losses)
            q_obs_t = torch.stack(q_obs)
            q_tgt_t = torch.stack(q_tgt)
            td = (q_tgt_t - q_obs_t).abs()
            loss = (weights * loss_vec).mean()
            td_for_priority = td.detach().cpu().numpy().tolist()
            q_mean = float(q_obs_t.mean().item())
        else:
            pred = []
            target = []
            for t in batch:
                q = self._current_scalar_q(t)
                bootstrap = self._next_value_scalar(t)
                y = torch.tensor(float(t.reward), device=self.device)
                if not t.terminal:
                    y = y + float(t.gamma_n) * bootstrap
                pred.append(q)
                target.append(y)
            pred_t = torch.stack(pred)
            target_t = torch.stack(target).detach()
            td_signed = target_t - pred_t
            loss_vec = nn.functional.smooth_l1_loss(pred_t, target_t, reduction="none")
            loss = (weights * loss_vec).mean()
            td_for_priority = td_signed.detach().abs().cpu().numpy().tolist()
            q_mean = float(pred_t.detach().mean().item())

        if not torch.isfinite(loss):
            raise FloatingPointError(f"Non-finite DQN loss: {loss}")
        loss.backward()
        grad_norm = float(nn.utils.clip_grad_norm_(self.online.parameters(), float(self.tcfg["gradient_clip_norm"])).item())
        self.optimizer.step()
        if bool(self.system.get("per", False)):
            self.replay.update_priorities(idx, td_for_priority)
        self.stats.updates += 1
        self.stats.gradient_steps += 1
        self.stats.loss_sum += float(loss.detach().item())
        self.stats.td_sum += float(np.mean(td_for_priority))
        self.stats.q_sum += q_mean
        self.stats.grad_norm_sum += grad_norm
        self.stats.train_seconds += time.perf_counter() - t0

    def parameter_delta_l2(self) -> float:
        ss = 0.0
        for name, p in self.online.state_dict().items():
            d = p.detach().cpu().float() - self.initial[name].float()
            ss += float((d * d).sum().item())
        return math.sqrt(ss)

    def summary(self) -> dict:
        n = max(1, self.stats.updates)
        total_actions = max(1, self.stats.epsilon_actions + self.stats.greedy_actions)
        return {
            "updates": self.stats.updates,
            "gradient_steps": self.stats.gradient_steps,
            "mean_loss": self.stats.loss_sum / n if self.stats.updates else None,
            "mean_abs_td": self.stats.td_sum / n if self.stats.updates else None,
            "mean_q": self.stats.q_sum / n if self.stats.updates else None,
            "mean_grad_norm": self.stats.grad_norm_sum / n if self.stats.updates else None,
            "train_seconds": self.stats.train_seconds,
            "act_seconds": self.stats.act_seconds,
            "epsilon_action_fraction": self.stats.epsilon_actions / total_actions,
            "greedy_action_fraction": self.stats.greedy_actions / total_actions,
            "epsilon_uniform_fraction": self.stats.epsilon_uniform_actions / max(1, self.stats.epsilon_actions),
            "epsilon_typeprior_fraction": self.stats.epsilon_typeprior_actions / max(1, self.stats.epsilon_actions),
            "epsilon_structured_fraction": self.stats.epsilon_structured_actions / max(1, self.stats.epsilon_actions),
            "epsilon_uniform_actions": self.stats.epsilon_uniform_actions,
            "epsilon_typeprior_actions": self.stats.epsilon_typeprior_actions,
            "epsilon_structured_actions": self.stats.epsilon_structured_actions,
            "replay_size": len(self.replay),
            "parameter_delta_l2": self.parameter_delta_l2(),
        }
