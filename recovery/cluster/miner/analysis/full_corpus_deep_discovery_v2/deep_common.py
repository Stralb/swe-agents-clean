from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import sparse

EXPECTED_CASES = 3809
EXPECTED_DB_SHA256 = "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa"
SEED = 20260829
REPO_SAMPLE_FRAC = 0.80

# Hard outcome-blinding barrier. Table names are checked before any content read.
FORBIDDEN_TABLE_PATTERNS = [
    r"scanner", r"finding", r"canonical", r"excluded", r"manual", r"risk",
    r"security", r"vulnerab", r"malicious", r"assessment", r"attribution",
    r"footprint", r"f1_f5", r"validation_result", r"review_result",
]

# Exact/substring column barriers. Deliberately do NOT block generic GitHub `labels`.
FORBIDDEN_COLUMN_PATTERNS = [
    r"^downstream_signal$", r"^final_label$", r"^review_notes$", r"^auto_tags$",
    r"scanner_", r"security_(finding|label|risk)", r"risk_(label|score|class)",
    r"malicious", r"canonical_finding", r"finding_producing", r"direct_side",
    r"side_effect", r"strict_mechanism", r"footprint", r"^f[1-5]_",
    r"manual_(category|label|class|review|correction)", r"provisional_.*risk",
]

# Columns that are usually subjective/manual when they appear in generic feature tables.
SUBJECTIVE_COLUMN_PATTERNS = [
    r"framing", r"specificity", r"scope", r"purpose_category", r"goal_alignment",
    r"implementation_pattern", r"case_evidence_summary", r"rationale", r"classification",
    r"human_review", r"correction", r"summary$",
]

IDENTIFIER_NAME_PATTERNS = [
    r"(^|_)id$", r"_id$", r"(^|_)url$", r"_url$", r"sha$", r"_sha$", r"_ref$",
    r"(^|_)number$", r"^number$", r"full_name$", r"html_url$",
]

TEXT_NAME_PATTERNS = [r"title", r"body", r"text", r"description", r"message", r"content", r"patch"]
TIME_NAME_PATTERNS = [r"_at$", r"date$", r"time$", r"timestamp$"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def save_sparse(path_base: Path, X: sparse.spmatrix, case_ids: np.ndarray, feature_names: Iterable[str] | None = None, meta: dict | None = None) -> None:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(path_base.with_suffix(".npz"), X.tocsr())
    np.save(path_base.with_name(path_base.name + "_case_ids.npy"), np.asarray(case_ids))
    if feature_names is not None:
        names = np.asarray(list(feature_names), dtype=object)
        np.save(path_base.with_name(path_base.name + "_features.npy"), names, allow_pickle=True)
    if meta is not None:
        write_json(path_base.with_name(path_base.name + "_meta.json"), meta)


def load_sparse(path_base: Path):
    X = sparse.load_npz(path_base.with_suffix(".npz")).tocsr()
    ids = np.load(path_base.with_name(path_base.name + "_case_ids.npy"), allow_pickle=True)
    fpath = path_base.with_name(path_base.name + "_features.npy")
    feats = np.load(fpath, allow_pickle=True).tolist() if fpath.exists() else None
    mpath = path_base.with_name(path_base.name + "_meta.json")
    meta = json.loads(mpath.read_text()) if mpath.exists() else {}
    return X, ids, feats, meta


def save_embedding(path_base: Path, E: np.ndarray, case_ids: np.ndarray, meta: dict | None = None) -> None:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    np.save(path_base.with_suffix(".npy"), np.asarray(E, dtype=np.float32))
    np.save(path_base.with_name(path_base.name + "_case_ids.npy"), np.asarray(case_ids))
    if meta is not None:
        write_json(path_base.with_name(path_base.name + "_meta.json"), meta)


def load_embedding(path_base: Path):
    E = np.load(path_base.with_suffix(".npy"), mmap_mode=None)
    ids = np.load(path_base.with_name(path_base.name + "_case_ids.npy"), allow_pickle=True)
    mpath = path_base.with_name(path_base.name + "_meta.json")
    meta = json.loads(mpath.read_text()) if mpath.exists() else {}
    return E, ids, meta


def normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def matches_any(name: str, patterns: Iterable[str]) -> bool:
    low = str(name or "").lower()
    return any(re.search(p, low) for p in patterns)


def table_forbidden(name: str) -> bool:
    return matches_any(name, FORBIDDEN_TABLE_PATTERNS)


def column_forbidden(name: str) -> bool:
    return matches_any(name, FORBIDDEN_COLUMN_PATTERNS)


def column_subjective(name: str) -> bool:
    return matches_any(name, SUBJECTIVE_COLUMN_PATTERNS)


def is_identifier_name(name: str) -> bool:
    return matches_any(name, IDENTIFIER_NAME_PATTERNS)


def is_text_name(name: str) -> bool:
    return matches_any(name, TEXT_NAME_PATTERNS)


def is_time_name(name: str) -> bool:
    return matches_any(name, TIME_NAME_PATTERNS)


def open_ro(db: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def list_tables(con: sqlite3.Connection) -> list[str]:
    return [str(r[0]) for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]


def table_columns(con: sqlite3.Connection, table: str) -> list[dict]:
    rows = con.execute(f"PRAGMA table_info({quote_ident(table)})").fetchall()
    return [{"cid": r[0], "name": str(r[1]), "type": str(r[2]), "notnull": r[3], "default": r[4], "pk": r[5]} for r in rows]


def quote_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def safe_columns_for_table(con: sqlite3.Connection, table: str, *, exclude_subjective: bool = True) -> list[str]:
    cols = [x["name"] for x in table_columns(con, table)]
    out = []
    for c in cols:
        if column_forbidden(c):
            continue
        if exclude_subjective and column_subjective(c):
            continue
        out.append(c)
    return out


def log_sql(log_path: Path, sql: str, table: str | None = None) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if table and table_forbidden(table):
        raise RuntimeError(f"FORBIDDEN_TABLE_ACCESS={table}")
    low = sql.lower()
    for p in FORBIDDEN_TABLE_PATTERNS:
        if re.search(p, low):
            # sqlite_master inventory statements are allowed; actual forbidden table reads are not.
            if "sqlite_master" not in low and "pragma table_info" not in low:
                raise RuntimeError(f"FORBIDDEN_SQL_PATTERN={p}")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {sql.strip()}\n")


def safe_read_sql(con: sqlite3.Connection, sql: str, log_path: Path, params=(), table: str | None = None) -> pd.DataFrame:
    log_sql(log_path, sql, table=table)
    return pd.read_sql_query(sql, con, params=params)


def robust_signed_log1p(x):
    if pd.isna(x):
        return np.nan
    x = float(x)
    return math.copysign(math.log1p(abs(x)), x)


def entropy(values: Iterable) -> float:
    c = Counter(values)
    n = sum(c.values())
    if n <= 0:
        return 0.0
    p = np.asarray([v / n for v in c.values() if v > 0], dtype=float)
    return float(-(p * np.log2(p)).sum())


def effective_number_from_counts(counts: Iterable[int]) -> float:
    a = np.asarray(list(counts), dtype=float)
    a = a[a > 0]
    if len(a) == 0:
        return 0.0
    p = a / a.sum()
    h = -(p * np.log(p)).sum()
    return float(np.exp(h))


def gini_from_counts(counts: Iterable[int]) -> float:
    x = np.asarray(list(counts), dtype=float)
    x = x[x >= 0]
    if len(x) == 0 or np.sum(x) == 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return float((2 * np.sum((np.arange(1, n + 1)) * x) / (n * np.sum(x))) - (n + 1) / n)


def repo_block_sample_indices(df: pd.DataFrame, rng: np.random.Generator, frac: float = REPO_SAMPLE_FRAC) -> np.ndarray:
    repos = pd.Series(df["repo_id"].dropna().unique())
    if len(repos) == 0:
        return np.arange(len(df))
    n = max(1, int(round(len(repos) * frac)))
    chosen = set(rng.choice(repos.to_numpy(), size=n, replace=False).tolist())
    return np.flatnonzero(df["repo_id"].isin(chosen).to_numpy())


def align_by_case_ids(base_ids: np.ndarray, ids: np.ndarray, arr):
    pos = {str(v): i for i, v in enumerate(ids)}
    idx = [pos.get(str(x), -1) for x in base_ids]
    if any(i < 0 for i in idx):
        missing = [str(base_ids[j]) for j, i in enumerate(idx) if i < 0][:20]
        raise RuntimeError(f"CASE_ALIGNMENT_MISSING={missing}")
    return arr[np.asarray(idx)]


def checkpoint_path(runroot: Path, stage: str) -> Path:
    return runroot / "checkpoints" / f"{stage}.json"


def checkpoint(runroot: Path, stage: str, status: str, detail: str = "", extra: dict | None = None) -> None:
    obj = {"stage": stage, "status": status, "detail": detail, "timestamp": now_iso()}
    if extra:
        obj.update(extra)
    write_json(checkpoint_path(runroot, stage), obj)


def stage_passed(runroot: Path, stage: str) -> bool:
    p = checkpoint_path(runroot, stage)
    if not p.exists():
        return False
    try:
        return json.loads(p.read_text()).get("status") == "PASS"
    except Exception:
        return False


def zscore_robust(x: pd.Series) -> pd.Series:
    s = pd.to_numeric(x, errors="coerce")
    med = s.median()
    mad = (s - med).abs().median()
    if pd.isna(mad) or mad <= 0:
        return pd.Series(np.zeros(len(s)), index=s.index, dtype=float)
    return 0.6744897501960817 * (s - med) / mad


def file_sha256s(root: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(root))
        if rel.endswith("SHA256SUMS.tsv"):
            continue
        try:
            h = sha256_file(p)
            rows.append({"path": rel, "bytes": p.stat().st_size, "sha256": h})
        except Exception as exc:
            rows.append({"path": rel, "bytes": None, "sha256": f"ERROR:{exc}"})
    return pd.DataFrame(rows)


def codeish_tokenize(text: str, normalize_identifiers: bool = False) -> list[str]:
    """Generic language-agnostic lexer. No semantic keyword list is imposed."""
    if not text:
        return []
    token_re = re.compile(
        r"(?:[A-Za-z_$][A-Za-z0-9_$]*)|(?:0x[0-9A-Fa-f]+)|(?:\d+(?:\.\d+)?)|"
        r"(?:==={0,1}|!==?|=>|<=|>=|&&|\|\||\+\+|--|\*\*|<<|>>|::|\?\?|\?\.|:=)|"
        r"(?:[^\sA-Za-z0-9_$])"
    )
    toks = token_re.findall(text)
    if not normalize_identifiers:
        return [t.lower() if re.match(r"^[A-Za-z_$]", t) else t for t in toks]
    out = []
    for t in toks:
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", t):
            # Preserve short lowercase alphabetic tokens only as raw lexical evidence in the raw view;
            # normalized view intentionally removes identifier semantics.
            out.append("ID")
        elif re.match(r"^(0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)$", t):
            out.append("NUM")
        else:
            out.append(t)
    return out


def normalize_text_for_similarity(text: str) -> str:
    s = str(text or "")
    s = re.sub(r"https?://\S+", " URL ", s)
    s = re.sub(r"\b[a-fA-F0-9]{12,64}\b", " HASH ", s)
    s = re.sub(r"\b\d+(?:\.\d+)?\b", " NUM ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def path_tokens(path: str) -> list[str]:
    p = str(path or "").replace("\\", "/").lower().strip("/")
    if not p:
        return []
    segs = [x for x in p.split("/") if x]
    toks = []
    for i, seg in enumerate(segs):
        toks.append(f"seg={seg}")
        toks.append(f"depth{i}={seg}")
        if "." in seg:
            parts = [x for x in re.split(r"[._\-]+", seg) if x]
            toks.extend(f"namepart={x}" for x in parts)
    if segs:
        name = segs[-1]
        ext = Path(name).suffix.lower() or "<none>"
        toks.append(f"ext={ext}")
        toks.append(f"depth={len(segs)}")
    for a, b in zip(segs, segs[1:]):
        toks.append(f"pathbigram={a}/{b}")
    return toks


def safe_filename(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s))[:180]
