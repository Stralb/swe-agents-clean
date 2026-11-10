from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import sparse

SEED = 20260829
REPO_SAMPLE_FRAC = 0.80
EXPECTED_CASES = 3809

FORBIDDEN_TABLE_RE = re.compile(r"scanner|finding|canonical|excluded|manual|risk|security|vulnerab|malicious|assessment|attribution|footprint|f1_f5", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding="utf-8")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_frame(df: pd.DataFrame, path_base: Path) -> str:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    pq = path_base.with_suffix(".parquet")
    try:
        df.to_parquet(pq, index=False)
        return str(pq)
    except Exception as exc:
        pk = path_base.with_suffix(".pkl")
        df.to_pickle(pk)
        path_base.with_suffix(".parquet_unavailable.txt").write_text(str(exc), encoding="utf-8")
        return str(pk)


def load_frame(path_base: Path) -> pd.DataFrame:
    pq = path_base.with_suffix(".parquet")
    pk = path_base.with_suffix(".pkl")
    if pq.exists():
        return pd.read_parquet(pq)
    if pk.exists():
        return pd.read_pickle(pk)
    raise FileNotFoundError(f"Missing frame base {path_base}")


def load_sparse(path_base: Path):
    X = sparse.load_npz(path_base.with_suffix(".npz")).tocsr()
    ids = np.load(path_base.with_name(path_base.name + "_case_ids.npy"), allow_pickle=True)
    fpath = path_base.with_name(path_base.name + "_features.npy")
    feats = np.load(fpath, allow_pickle=True).tolist() if fpath.exists() else None
    mpath = path_base.with_name(path_base.name + "_meta.json")
    meta = json.loads(mpath.read_text()) if mpath.exists() else {}
    return X, ids, feats, meta


def align_sparse_rows(base_ids: np.ndarray, ids: np.ndarray, X: sparse.spmatrix) -> sparse.csr_matrix:
    pos = {str(v): i for i, v in enumerate(ids)}
    idx = np.asarray([pos.get(str(x), -1) for x in base_ids], dtype=int)
    if np.any(idx < 0):
        missing = [str(base_ids[i]) for i in np.flatnonzero(idx < 0)[:20]]
        raise RuntimeError(f"CASE_ALIGNMENT_MISSING={missing}")
    return X.tocsr()[idx]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_block_sample_indices(df: pd.DataFrame, rng: np.random.Generator, frac: float = REPO_SAMPLE_FRAC) -> np.ndarray:
    repos = pd.Series(df["repo_id"].dropna().unique())
    if len(repos) == 0:
        return np.arange(len(df))
    n = max(1, int(round(len(repos) * frac)))
    chosen = set(rng.choice(repos.to_numpy(), size=n, replace=False).tolist())
    return np.flatnonzero(df["repo_id"].isin(chosen).to_numpy())


def effective_number(counts: Iterable[int]) -> float:
    a = np.asarray(list(counts), dtype=float)
    a = a[a > 0]
    if not len(a):
        return 0.0
    p = a / a.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


def bh_fdr(pvals: np.ndarray) -> np.ndarray:
    p = np.asarray(pvals, dtype=float)
    out = np.full(len(p), np.nan)
    valid = np.isfinite(p)
    if not valid.any():
        return out
    pv = p[valid]
    order = np.argsort(pv)
    ranked = pv[order]
    m = len(ranked)
    q = ranked * m / np.arange(1, m + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    back = np.empty(m, dtype=float)
    back[order] = q
    out[np.flatnonzero(valid)] = back
    return out


def feature_source(name: str) -> str:
    n = str(name)
    if n.startswith("template__"): return "template"
    if n.startswith("align_"): return "artifact_alignment"
    if n.startswith("text__"): return "text_latent"
    if n.startswith("paths__"): return "path_latent"
    if n.startswith("patch__"): return "patch_latent"
    if n.startswith("syntax__"): return "syntax_latent"
    if n.startswith("structured__"): return "structured_latent"
    if n.startswith("fused_"): return "fused_latent"
    if n.startswith("repo__"): return "repository"
    if n.startswith("issue__"): return "issue"
    if n.startswith("pr__"): return "pull_request"
    if n.startswith("rel__"): return "relational"
    if n.startswith("path_"): return "path_metric"
    if n.startswith("patch_"): return "patch_metric"
    if n.startswith("syntax_"): return "syntax_metric"
    if n.startswith("delta_hours__"): return "time_delta"
    return "other"


def feature_root(name: str) -> str:
    n = str(name).lower()
    n = re.sub(r"^(signed_)?log1p_", "", n)
    n = re.sub(r"__(mean|min|max|sum|std|nonmissing|nunique|top_share|strlen_mean|strlen_max)$", "", n)
    n = re.sub(r"_(mean|min|max|sum|std|count|ratio|fraction|share|entropy)$", "", n)
    return n


def is_generated_assignment(name: str) -> bool:
    n = str(name).lower()
    return bool(re.search(r"(?:^template__|^fused_|__(?:kmeans|hdbscan|iso|lof|topic|topic_weight)$|cluster|assignment)", n))


def feature_role(name: str) -> str:
    """Classify a feature by analytical provenance, not by domain meaning.

    primary_observed: objective/raw or deterministic measurements that may enter generic
      relationship/pattern/temporal discovery.
    generated_model: assignments, anomaly scores, topic weights, and template memberships
      produced by v2 models. They are preserved for decoding/controls but excluded from the
      primary discovery matrix to avoid circular findings such as 'cluster X predicts topic X'.
    provenance_text: latent features derived from the AI-marker evidence text. They are useful
      for stratification/provenance controls, but not ranked as software-development discoveries.
    """
    n = str(name).lower()
    if is_generated_assignment(n):
        return "generated_model"
    if "reltext_ai_markers_marker_text" in n:
        return "provenance_text"
    if n.startswith("rel__ai_markers__") or "upstream_features__has_ai_marker" in n:
        return "provenance_metadata"
    return "primary_observed"


def infer_kind(s: pd.Series, name: str = "") -> str:
    non = s.dropna()
    nun = int(non.nunique())
    if nun <= 1:
        return "constant"
    if is_generated_assignment(name):
        return "categorical"
    if pd.api.types.is_numeric_dtype(s):
        vals = pd.to_numeric(non, errors="coerce").dropna()
        uniq = set(vals.unique().tolist())
        if nun == 2 and uniq.issubset({0, 1, 0.0, 1.0}):
            return "binary"
        return "numeric"
    if nun <= 100:
        return "categorical"
    return "high_cardinality"


def checkpoint(v21root: Path, stage: str, status: str, detail: str = "", extra: dict | None = None) -> None:
    obj = {"stage": stage, "status": status, "detail": detail, "timestamp": now_iso()}
    if extra:
        obj.update(extra)
    write_json(v21root / "checkpoints" / f"{stage}.json", obj)


def passed(v21root: Path, stage: str) -> bool:
    p = v21root / "checkpoints" / f"{stage}.json"
    if not p.exists(): return False
    try: return json.loads(p.read_text()).get("status") == "PASS"
    except Exception: return False


def assert_source_blind(source: Path) -> dict:
    status_path = source / "00_manifest" / "FINAL_STATUS_V2.json"
    if not status_path.exists():
        raise RuntimeError("SOURCE_FINAL_STATUS_MISSING")
    status = json.loads(status_path.read_text())
    if status.get("status") != "PASS" or not status.get("deep_discovery_complete"):
        raise RuntimeError(f"SOURCE_NOT_COMPLETE={status}")
    if status.get("outcome_overlay_performed") is not False or status.get("security_outcomes_read") is not False:
        raise RuntimeError(f"SOURCE_NOT_OUTCOME_BLIND={status}")
    access = source / "00_manifest" / "TABLE_ACCESS_AUDIT.csv"
    if not access.exists():
        raise RuntimeError("TABLE_ACCESS_AUDIT_MISSING")
    a = pd.read_csv(access)
    violations = []
    for _, r in a.iterrows():
        table = str(r.get("table", ""))
        statusv = str(r.get("status", ""))
        if FORBIDDEN_TABLE_RE.search(table) and not statusv.startswith("BLOCKED"):
            violations.append({"table": table, "status": statusv})
    if violations:
        raise RuntimeError(f"OUTCOME_BLINDING_VIOLATION={violations[:20]}")
    return status


def safe_name(x: str, maxlen: int = 180) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(x))[:maxlen]
