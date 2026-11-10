from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


@dataclass(frozen=True)
class QNetConfig:
    state_dim: int
    action_dim: int
    hidden_dim: int = 128
    dueling: bool = False
    distributional: bool = False
    atoms: int = 51
    vmin: float = 0.0
    vmax: float = 5.0


class ActionValueNetwork(nn.Module):
    """Scores a variable legal action set using shared state/action features.

    This head preserves the entire legal ARC action set. The caller supplies one
    row per legal action. Dueling is implemented over that supplied legal set,
    so the centering term is the mean advantage of currently legal actions.
    """

    def __init__(self, cfg: QNetConfig):
        super().__init__()
        self.cfg = cfg
        self.state = nn.Sequential(
            nn.Linear(cfg.state_dim, cfg.hidden_dim),
            nn.ReLU(),
            nn.Linear(cfg.hidden_dim, cfg.hidden_dim),
            nn.ReLU(),
        )
        self.action = nn.Sequential(
            nn.Linear(cfg.action_dim, cfg.hidden_dim // 2),
            nn.ReLU(),
        )
        fused = cfg.hidden_dim + cfg.hidden_dim // 2
        out_dim = cfg.atoms if cfg.distributional else 1
        self.adv = nn.Sequential(
            nn.Linear(fused, cfg.hidden_dim),
            nn.ReLU(),
            nn.Linear(cfg.hidden_dim, out_dim),
        )
        self.value = None
        if cfg.dueling:
            self.value = nn.Sequential(
                nn.Linear(cfg.hidden_dim, cfg.hidden_dim),
                nn.ReLU(),
                nn.Linear(cfg.hidden_dim, out_dim),
            )
        if cfg.distributional:
            self.register_buffer("support", torch.linspace(cfg.vmin, cfg.vmax, cfg.atoms))

    def logits(self, state: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        """Return [N] scalar Q values or [N, atoms] logits for one state."""
        if state.ndim != 1:
            raise ValueError(f"state must be 1-D, got {tuple(state.shape)}")
        if actions.ndim != 2:
            raise ValueError(f"actions must be 2-D, got {tuple(actions.shape)}")
        s = self.state(state.unsqueeze(0)).expand(actions.shape[0], -1)
        a = self.action(actions)
        adv = self.adv(torch.cat([s, a], dim=-1))
        if self.value is not None:
            val = self.value(s[:1])
            adv = val + adv - adv.mean(dim=0, keepdim=True)
        if not self.cfg.distributional:
            return adv.squeeze(-1)
        return adv

    def q_values(self, state: torch.Tensor, actions: torch.Tensor) -> torch.Tensor:
        out = self.logits(state, actions)
        if not self.cfg.distributional:
            return out
        probs = torch.softmax(out, dim=-1)
        return (probs * self.support).sum(dim=-1)

    def action_distribution(self, state: torch.Tensor, action: torch.Tensor) -> torch.Tensor:
        if not self.cfg.distributional:
            raise RuntimeError("action_distribution only valid for distributional network")
        logits = self.logits(state, action.unsqueeze(0))[0]
        return torch.softmax(logits, dim=-1)


def c51_project(
    next_prob: torch.Tensor,
    reward: torch.Tensor,
    terminal: torch.Tensor,
    gamma_n: torch.Tensor,
    support: torch.Tensor,
    vmin: float,
    vmax: float,
) -> torch.Tensor:
    """Project Bellman-updated categorical distributions onto fixed support.

    Shapes: next_prob [B, A], reward/terminal/gamma_n [B], support [A].
    """
    if next_prob.ndim != 2:
        raise ValueError("next_prob must be [B, atoms]")
    bsz, atoms = next_prob.shape
    if support.numel() != atoms:
        raise ValueError("support/atom mismatch")
    dz = (vmax - vmin) / (atoms - 1)
    tz = reward[:, None] + (1.0 - terminal[:, None]) * gamma_n[:, None] * support[None, :]
    tz = tz.clamp(vmin, vmax)
    bj = (tz - vmin) / dz
    lo = bj.floor().long()
    hi = bj.ceil().long()
    proj = torch.zeros_like(next_prob)
    offset = torch.arange(bsz, device=next_prob.device)[:, None] * atoms
    flat = proj.view(-1)
    pflat = next_prob
    eq = hi == lo
    flat.index_add_(0, (lo + offset).view(-1), (pflat * (hi.float() - bj + eq.float())).view(-1))
    flat.index_add_(0, (hi + offset).view(-1), (pflat * (bj - lo.float())).view(-1))
    return proj
