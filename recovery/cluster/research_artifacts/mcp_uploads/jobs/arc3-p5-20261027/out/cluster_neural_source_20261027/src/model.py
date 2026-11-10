"""Representation interface + provisional V0 (plan 5.2) and the DQN / PPO heads.

Contract:  Representation.forward(ObsBatch) -> RepresentationOutput(spatial, pooled, meta)
    spatial : optional [B, C, 64, 64] local features (needed by the click head)
    pooled  : [B, D] state vector (whole-board summary + permitted scalar/action context)
Heads consume that output only. Nothing in the adapter, DQN Bellman update or PPO objective knows which
representation is active; a new one is: implementation + entry in _ARCHS + config + its own test.

V0 = categorical-colour CNN, current+previous frame+diff, whole-board context broadcast into the click head.
It is a *pipeline-validation scaffold*, not the selected architecture (plan 5.2 / 7.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .adapter import GRID, N_ACTIONS, N_CLICK, N_SIMPLE, N_TYPES, Observation

NCOL = 16          # colour ids observed 0-12; 16 leaves headroom


@dataclass
class ObsBatch:
    frame: torch.Tensor        # long [B,64,64]
    prev_frame: torch.Tensor   # long [B,64,64]
    prev_action: torch.Tensor  # long [B]  (-1 = none)
    progress: torch.Tensor     # float [B,2]  (progress, high_water)
    mask: torch.Tensor         # bool [B,N_ACTIONS]


def collate(obs: list) -> ObsBatch:
    return ObsBatch(
        torch.from_numpy(np.stack([o.frame for o in obs])).long(),
        torch.from_numpy(np.stack([o.prev_frame for o in obs])).long(),
        torch.tensor([o.prev_action for o in obs], dtype=torch.long),
        torch.tensor([[o.progress, o.high_water] for o in obs], dtype=torch.float32),
        torch.from_numpy(np.stack([o.mask for o in obs])),
    )


@dataclass
class RepresentationOutput:
    pooled: torch.Tensor
    spatial: Optional[torch.Tensor] = None
    meta: dict = field(default_factory=dict)


def _context(b: ObsBatch) -> torch.Tensor:
    """Permitted scalar/action context: progress, high-water, previous action type (one-hot, 0 = none), click xy."""
    a = b.prev_action
    typ = torch.where(a < 0, torch.zeros_like(a), torch.where(a < N_SIMPLE, a + 1, torch.full_like(a, N_SIMPLE + 1)))
    k = (a - N_SIMPLE).clamp(min=0)
    click = (a >= N_SIMPLE).float().unsqueeze(1)
    xy = torch.stack([(k % GRID).float(), (k // GRID).float()], 1) / (GRID - 1) * click
    return torch.cat([b.progress / 10.0, F.one_hot(typ, N_TYPES + 1).float(), xy], 1)


class OneHotCNN(nn.Module):
    """Four 3x3 stride-1 convs at full resolution (9x9 receptive field), pooled whole-board vector + context."""

    def __init__(self, channels: int = 32, context_dim: int = 128, use_prev: bool = True):
        super().__init__()
        self.use_prev = use_prev
        cin = NCOL * 2 + 1 if use_prev else NCOL
        layers, c = [], cin
        for _ in range(4):
            layers += [nn.Conv2d(c, channels, 3, padding=1), nn.ReLU()]
            c = channels
        self.convs = nn.Sequential(*layers).to(memory_format=torch.channels_last)   # ~20% faster on CPU
        self.fc = nn.Linear(2 * channels + 2 + (N_TYPES + 1) + 2, context_dim)
        self.spatial_channels, self.out_dim = channels, context_dim

    def forward(self, b: ObsBatch) -> RepresentationOutput:
        x = F.one_hot(b.frame.clamp(0, NCOL - 1), NCOL).permute(0, 3, 1, 2).float()
        if self.use_prev:
            p = F.one_hot(b.prev_frame.clamp(0, NCOL - 1), NCOL).permute(0, 3, 1, 2).float()
            diff = (b.frame != b.prev_frame).float().unsqueeze(1)
            x = torch.cat([x, p, diff], 1)
        h = self.convs(x)
        g = torch.cat([h.mean((2, 3)), h.amax((2, 3))], 1)
        pooled = F.relu(self.fc(torch.cat([g, _context(b)], 1)))
        return RepresentationOutput(pooled=pooled, spatial=h, meta={"history": 2 if self.use_prev else 1})


_ARCHS = {
    "onehotcnn_stack2": lambda a: OneHotCNN(a["channels"], a["context_dim"], use_prev=True),
    "onehotcnn_stack1": lambda a: OneHotCNN(a["channels"], a["context_dim"], use_prev=False),
}


def build_representation(arch: dict) -> nn.Module:
    """Resolved once at run start (no per-step config parsing)."""
    return _ARCHS[arch["id"]](arch)


class ClickHead(nn.Module):
    """Local features + broadcast whole-board context -> one logit/value per pixel (index y*64+x).

    conv1x1([spatial ; broadcast(pooled)]) is computed as conv1x1(spatial) + linear(pooled) broadcast:
    the same function, without materialising the broadcast tensor (about 2x cheaper on CPU)."""

    def __init__(self, c_local: int, d_ctx: int, hidden: int = 32):
        super().__init__()
        self.local = nn.Conv2d(c_local, hidden, 1)
        self.ctx = nn.Linear(d_ctx, hidden)
        self.out = nn.Conv2d(hidden, 1, 1)

    def forward(self, rep: RepresentationOutput) -> torch.Tensor:
        if rep.spatial is None:
            raise ValueError("click head needs a spatial view from the representation")
        h = F.relu(self.local(rep.spatial) + self.ctx(rep.pooled)[:, :, None, None])
        return self.out(h).flatten(1)


class QNet(nn.Module):
    """DQN head: Q over the full 4102-action space (6 simple, then 4096 clicks)."""

    def __init__(self, arch: dict):
        super().__init__()
        self.rep = build_representation(arch)
        self.simple = nn.Linear(self.rep.out_dim, N_SIMPLE)
        self.click = ClickHead(self.rep.spatial_channels, self.rep.out_dim)

    def forward(self, b: ObsBatch) -> torch.Tensor:
        r = self.rep(b)
        return torch.cat([self.simple(r.pooled), self.click(r)], 1)


class ActorCritic(nn.Module):
    """PPO head: logits over 7 action types, conditional logits over 4096 click locations, and a value."""

    def __init__(self, arch: dict):
        super().__init__()
        self.rep = build_representation(arch)
        self.type_head = nn.Linear(self.rep.out_dim, N_TYPES)
        self.click = ClickHead(self.rep.spatial_channels, self.rep.out_dim)
        self.value = nn.Linear(self.rep.out_dim, 1)

    def forward(self, b: ObsBatch):
        r = self.rep(b)
        return self.type_head(r.pooled), self.click(r), self.value(r.pooled).squeeze(1)


def model_info(net: nn.Module, arch: dict) -> dict:
    return {"architecture": arch["id"], "arch_config": arch, "parameters": sum(p.numel() for p in net.parameters())}


assert N_ACTIONS == N_SIMPLE + N_CLICK
