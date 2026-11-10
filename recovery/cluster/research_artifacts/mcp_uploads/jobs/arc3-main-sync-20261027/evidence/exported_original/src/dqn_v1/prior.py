"""Frozen representation/effect model used by the selected DQN V1 baseline.

This is the selected one-hot CNN + two-frame stack + vector action interface.
Only the selected architecture is retained here; the original architecture-search
code is intentionally not vendored into the team repository.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

GLOB = 128
SPAT = 96


class OneHotCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(16, 32, 5, 2, 2), nn.GELU(),
            nn.Conv2d(32, 64, 3, 2, 1), nn.GELU(),
            nn.Conv2d(64, SPAT, 3, 2, 1), nn.GELU(),
        )
        self.proj = nn.Linear(SPAT, GLOB)

    def encode(self, grid):
        x = F.one_hot(grid.long().clamp(0, 15), num_classes=16).float().permute(0, 3, 1, 2).contiguous()
        s = self.conv(x)
        return self.proj(s.mean((2, 3))), s


class Stack2Temporal(nn.Module):
    def __init__(self):
        super().__init__()
        self.base = OneHotCNN()
        self.gf = nn.Linear(GLOB * 2, GLOB)
        self.sf = nn.Conv2d(SPAT * 2, SPAT, 1)

    def forward(self, grid, prev_grid, hist_grid, hist_mask):
        g, s = self.base.encode(grid)
        pg, ps = self.base.encode(prev_grid)
        return self.gf(torch.cat([g, pg], -1)), self.sf(torch.cat([s, ps], 1))


class GenericActionContext(nn.Module):
    def __init__(self):
        super().__init__()
        self.aid = nn.Embedding(8, 16)
        self.x = nn.Embedding(65, 16)
        self.y = nn.Embedding(65, 16)
        self.mlp = nn.Sequential(nn.Linear(48, 64), nn.GELU(), nn.Linear(64, 64))

    def forward(self, action):
        aid = action[:, 0].long().clamp(0, 7)
        is6 = aid == 6
        xi = torch.where(is6, (action[:, 1].clamp(0, 1) * 63).round().long(), torch.full_like(aid, 64))
        yi = torch.where(is6, (action[:, 2].clamp(0, 1) * 63).round().long(), torch.full_like(aid, 64))
        return self.mlp(torch.cat([self.aid(aid), self.x(xi), self.y(yi)], -1))


class VectorInterface(nn.Module):
    def __init__(self):
        super().__init__()
        self.ctx = GenericActionContext()
        self.head = nn.Sequential(nn.Linear(GLOB + 64, 128), nn.GELU(), nn.Linear(128, 1))

    def forward(self, g, s, action):
        c = self.ctx(action)
        return self.head(torch.cat([g, c], -1)).squeeze(-1), c

    def score_all_action6(self, g, s):
        y, x = torch.meshgrid(torch.arange(64, device=g.device), torch.arange(64, device=g.device), indexing="ij")
        a = torch.stack([torch.full_like(x, 6), x, y], -1).reshape(-1, 3).float()
        a[:, 1:3] /= 63.0
        outs = []
        for b in range(g.shape[0]):
            c = self.ctx(a)
            gg = g[b:b + 1].expand(4096, -1)
            outs.append(self.head(torch.cat([gg, c], -1)).squeeze(-1).reshape(64, 64))
        return torch.stack(outs, 0)


class SelectedEffectModel(nn.Module):
    """Module names deliberately match the original checkpoint state_dict."""

    def __init__(self):
        super().__init__()
        self.temporal = Stack2Temporal()
        self.action = VectorInterface()


PUBLIC_GAMES = [
    "ar25", "bp35", "dc22", "ft09", "g50t", "ka59", "lf52", "lp85", "r11l", "s5i5",
    "sb26", "sk48", "su15", "tn36", "tr87", "tu93", "vc33", "cd82", "ls20", "m0r0",
    "sp80", "re86", "cn04", "wa30", "sc25",
]
PUBLIC_FOLDS = [
    ["bp35", "sb26", "tu93", "sk48", "r11l"],
    ["vc33", "tn36", "tr87", "wa30", "s5i5"],
    ["lf52", "ls20", "su15", "ar25", "sp80"],
    ["dc22", "re86", "ka59", "lp85", "g50t"],
    ["sc25", "ft09", "cn04", "cd82", "m0r0"],
]
CHECKPOINT_STEM = "E-onehotcnn__T-stack2__A-vector__U-effect"


def fold_for_game(game: str) -> int:
    for i, games in enumerate(PUBLIC_FOLDS):
        if game in games:
            return i
    raise ValueError(
        f"DQN V1 currently reproduces the selected public cross-fold baseline only; "
        f"no frozen deployment checkpoint exists for unknown game {game!r}."
    )


def load_prior(game: str, assets_root: Path, device: torch.device):
    fold = fold_for_game(game)
    path = assets_root / "checkpoints" / f"{CHECKPOINT_STEM}__f{fold}__s11.pt"
    obj = torch.load(path, map_location="cpu", weights_only=False)
    model = SelectedEffectModel()
    model.load_state_dict(obj["state_dict"], strict=True)
    model.to(device).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model, fold, path


def state_outputs(model, grid: np.ndarray, prev: np.ndarray, available: list[int], device: torch.device):
    gt = torch.from_numpy(np.asarray(grid, dtype=np.int64)).unsqueeze(0).to(device)
    pt = torch.from_numpy(np.asarray(prev, dtype=np.int64)).unsqueeze(0).to(device)
    hg = torch.zeros((1, 4, 64, 64), dtype=torch.long, device=device)
    hm = torch.zeros((1, 4), dtype=torch.bool, device=device)
    with torch.no_grad():
        g, s = model.temporal(gt, pt, hg, hm)
        emb = F.normalize(g, dim=-1)[0].cpu().numpy().astype(np.float32)
        simple = [a for a in available if a != 6]
        simple_logits = np.empty((0,), dtype=np.float32)
        if simple:
            av = np.asarray([[float(a), -1.0, -1.0] for a in simple], dtype=np.float32)
            at = torch.from_numpy(av).to(device)
            out, _ = model.action(g.expand(len(simple), -1), s.expand(len(simple), -1, -1, -1), at)
            simple_logits = out.cpu().numpy().astype(np.float32)
        a6_logits = model.action.score_all_action6(g, s)[0].cpu().numpy().astype(np.float32) if 6 in available else None
    return emb, simple, simple_logits, a6_logits
