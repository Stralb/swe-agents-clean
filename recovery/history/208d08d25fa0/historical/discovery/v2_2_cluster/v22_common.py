from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

import numpy as np
import pandas as pd

EXPECTED_CASES = 3809
EXPECTED_DB_SHA256 = "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa"
SEED = 20260830

CODE_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts",
    ".py", ".go", ".java", ".rs", ".rb", ".php", ".cs", ".kt", ".kts",
    ".swift", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hh", ".sh",
    ".bash", ".zsh", ".sql", ".vue", ".svelte",
}

GENERATED_BASENAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "pnpm-lock.yml",
    "yarn.lock", "bun.lock", "bun.lockb", "composer.lock", "cargo.lock",
    "poetry.lock", "pipfile.lock", "uv.lock", "gemfile.lock", "pubspec.lock",
}
GENERATED_SUFFIXES = {".min.js", ".min.css", ".map", ".snap"}
GENERATED_PATH_PARTS = {"vendor", "dist", "build", "coverage", "node_modules"}

JS_KEYWORDS = {
    "if","else","for","while","do","switch","case","default","return","throw","try","catch","finally",
    "break","continue","function","class","extends","new","const","let","var","async","await","yield",
    "import","export","from","as","in","of","instanceof","typeof","void","delete","this","super",
    "true","false","null","undefined","interface","type","enum","implements","public","private","protected",
    "static","readonly","abstract","declare","namespace","module","satisfies","keyof","infer","unknown","never",
}
OTHER_KEYWORDS = {
    "def","lambda","with","pass","raise","except","elif","and","or","not","is","none","match","when",
    "func","struct","package","defer","go","select","range","map","chan","fn","impl","trait","pub","mut",
}
KEYWORDS = JS_KEYWORDS | OTHER_KEYWORDS
CONTROL_CALL_EXCLUDE = {"if","for","while","switch","catch","function","return","typeof","new","await"}

TOKEN_RE = re.compile(
    r"(?:[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)"
    r"|(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)"
    r"|(?:===|!==|==|!=|=>|<=|>=|&&|\|\||\?\?|\?\.|\+\+|--|\+=|-=|\*=|/=|%=|\*\*|<<|>>|>>>|[+\-*/%<>=!&|?:~^])"
)
CALL_RE = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*){0,4})\s*\(")
IMPORT_FROM_RE = re.compile(r"\bfrom\s+['\"]([^'\"]+)['\"]")
REQUIRE_RE = re.compile(r"\b(?:require|import)\s*\(\s*['\"]([^'\"]+)['\"]\s*\)")
SIDE_EFFECT_IMPORT_RE = re.compile(r"^\s*import\s+['\"]([^'\"]+)['\"]")
STATIC_IMPORT_RE = re.compile(r"^\s*import\s+.+?\s+from\s+['\"]([^'\"]+)['\"]")
DEP_PAIR_RE = re.compile(r"^\s*['\"]?(@?[A-Za-z0-9_.\-/]+)['\"]?\s*:\s*['\"]([^'\"]+)['\"]\s*,?\s*$")

STOPWORDS = {
    "the","a","an","and","or","to","of","in","on","for","with","is","are","was","were","be","been","being",
    "this","that","these","those","it","its","as","at","by","from","we","you","i","they","he","she","them",
    "our","your","their","can","could","should","would","will","may","might","not","no","yes","do","does","did",
    "fix","add","update","change","remove","use","make","support","issue","pr","pull","request","code",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, default=str), encoding="utf-8")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_frame(df: pd.DataFrame, base: Path) -> str:
    base.parent.mkdir(parents=True, exist_ok=True)
    pq = base.with_suffix(".parquet")
    try:
        df.to_parquet(pq, index=False)
        return str(pq)
    except Exception as exc:
        pk = base.with_suffix(".pkl")
        df.to_pickle(pk)
        base.with_suffix(".parquet_unavailable.txt").write_text(repr(exc), encoding="utf-8")
        return str(pk)


def load_frame(base: Path) -> pd.DataFrame:
    pq = base.with_suffix(".parquet")
    pk = base.with_suffix(".pkl")
    if pq.exists():
        return pd.read_parquet(pq)
    if pk.exists():
        return pd.read_pickle(pk)
    raise FileNotFoundError(str(base))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bh_fdr(pvals):
    arr = np.asarray(pvals, dtype=float)
    out = np.full(len(arr), np.nan)
    idx = np.flatnonzero(np.isfinite(arr))
    if len(idx) == 0:
        return out
    p = arr[idx]
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * len(ranked) / (np.arange(len(ranked)) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q = np.clip(q, 0, 1)
    temp = np.empty(len(q))
    temp[order] = q
    out[idx] = temp
    return out


def is_generated_path(filename: str) -> bool:
    s = str(filename or "").replace("\\", "/").lower()
    base = s.rsplit("/", 1)[-1]
    if base in GENERATED_BASENAMES:
        return True
    if any(base.endswith(x) for x in GENERATED_SUFFIXES):
        return True
    parts = set(x for x in s.split("/") if x)
    return bool(parts & GENERATED_PATH_PARTS)


def is_code_path(filename: str) -> bool:
    s = str(filename or "").replace("\\", "/").lower()
    base = s.rsplit("/", 1)[-1]
    if is_generated_path(s):
        return False
    # handle multi-suffix names like .d.ts through final suffix
    ext = "." + base.rsplit(".", 1)[-1] if "." in base else ""
    return ext in CODE_EXTS


def ext_of(filename: str) -> str:
    s = str(filename or "").replace("\\", "/").lower()
    base = s.rsplit("/", 1)[-1]
    if "." not in base:
        return "<none>"
    return "." + base.rsplit(".", 1)[-1]


def parse_unified_patch(patch: str):
    """Yield hunks; each hunk is a list of (op, text)."""
    hunks=[]; cur=[]; in_hunk=False
    for raw in str(patch or "").splitlines():
        if raw.startswith("@@"):
            if cur: hunks.append(cur)
            cur=[]; in_hunk=True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            cur.append(("+", raw[1:]))
        elif raw.startswith("-"):
            cur.append(("-", raw[1:]))
        else:
            cur.append(("=", raw[1:] if raw.startswith(" ") else raw))
    if cur: hunks.append(cur)
    return hunks


def change_blocks_from_hunk(hunk):
    """Split a hunk into maximal +/- runs separated by context; returns dicts."""
    blocks=[]; rem=[]; add=[]
    def flush():
        nonlocal rem,add
        if rem or add:
            blocks.append({"removed":rem,"added":add})
        rem=[]; add=[]
    for op,text in hunk:
        if op == "=":
            flush()
        elif op == "-":
            rem.append(text)
        elif op == "+":
            add.append(text)
    flush()
    return blocks


def calls_in_text(text: str):
    out=[]
    for m in CALL_RE.finditer(str(text or "")):
        c=m.group(1)
        if c.split(".",1)[0] in CONTROL_CALL_EXCLUDE:
            continue
        if len(c) <= 1:
            continue
        out.append(c)
    return out


def import_modules(text: str):
    out=[]
    for line in str(text or "").splitlines():
        for rx in (STATIC_IMPORT_RE, SIDE_EFFECT_IMPORT_RE, IMPORT_FROM_RE, REQUIRE_RE):
            m=rx.search(line)
            if m:
                out.append(m.group(1)); break
    return out


def lexical_features(text: str):
    toks=TOKEN_RE.findall(str(text or ""))
    kws=[]; ops=[]
    for t in toks:
        if t in KEYWORDS:
            kws.append(t)
        elif re.fullmatch(r"===|!==|==|!=|=>|<=|>=|&&|\|\||\?\?|\?\.|\+\+|--|\+=|-=|\*=|/=|%=|\*\*|<<|>>|>>>|[+\-*/%<>=!&|?:~^]", t):
            ops.append(t)
    return kws,ops


def word_tokens(text: str):
    xs=re.findall(r"[A-Za-z_$][A-Za-z0-9_$.-]{1,}", str(text or "").lower())
    return [x for x in xs if x not in STOPWORDS and len(x) >= 2]


def normalized_block(lines):
    """API-preserving code skeleton: literals/local identifiers normalized; dotted/call names retained."""
    text="\n".join(str(x) for x in lines)
    # strip comments lightly
    text=re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text=re.sub(r"(^|\s)//.*", " ", text)
    text=re.sub(r"(^|\s)#.*", " ", text)
    # strings and numbers
    text=re.sub(r"`(?:\\.|[^`])*`", " STR ", text)
    text=re.sub(r"'(?:\\.|[^'])*'", " STR ", text)
    text=re.sub(r'"(?:\\.|[^"])*"', " STR ", text)
    text=re.sub(r"\b(?:0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)\b", " NUM ", text)
    call_spans={m.start(1):m.group(1) for m in CALL_RE.finditer(text)}
    # token replacement while preserving keywords and function/property names
    parts=[]; pos=0
    for m in re.finditer(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", text):
        parts.append(text[pos:m.start()])
        tok=m.group(0)
        preserve=(tok in KEYWORDS or m.start() in call_spans or "." in tok)
        parts.append(tok if preserve else "ID")
        pos=m.end()
    parts.append(text[pos:])
    norm="".join(parts)
    norm=re.sub(r"\s+", " ", norm).strip()
    return norm


def path_items(filename: str):
    s=str(filename or "").replace("\\","/").strip("/").lower()
    if not s: return set()
    parts=[p for p in s.split("/") if p]
    base=parts[-1]
    out={f"ext:{ext_of(s)}", f"base:{base}"}
    if parts:
        out.add(f"top:{parts[0]}")
    for seg in parts[:-1]:
        if seg and len(seg)<=40:
            out.add(f"seg:{seg}")
    return out


def safe_ratio(a,b):
    return float(a/b) if b else np.nan


def effective_repositories(counts):
    x=np.asarray(list(counts),dtype=float)
    x=x[x>0]
    if not len(x): return 0.0
    p=x/x.sum(); return float(np.exp(-(p*np.log(p)).sum()))


def rank_percentile(s: pd.Series):
    return s.rank(pct=True, method="average")
