from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import sqlite3
import statistics
import sys
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy import stats
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import pdist, squareform
except Exception as exc:
    raise SystemExit(f"CORE_DEPENDENCY_MISSING scipy: {exc}")

try:
    from sklearn.cluster import KMeans, AgglomerativeClustering
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import NMF, PCA
    from sklearn.metrics import (
        adjusted_rand_score,
        normalized_mutual_info_score,
        silhouette_score,
        calinski_harabasz_score,
        davies_bouldin_score,
        mutual_info_score,
    )
    from sklearn.neighbors import LocalOutlierFactor
    from sklearn.preprocessing import RobustScaler
except Exception as exc:
    raise SystemExit(f"CORE_DEPENDENCY_MISSING scikit-learn: {exc}")

try:
    from joblib import Parallel, delayed
except Exception:
    Parallel = None
    delayed = None

EXPECTED_CASES = 3809
EXPECTED_DB_SHA256 = "126860eeb6e55786a2db29e4010672749cce58f29f511459d40166a1b07936fa"
SEED = 20260829
RESAMPLES = 200
REPO_SAMPLE_FRAC = 0.80
GOWER_RESAMPLES = 50
TEXT_TOPIC_KS = [5, 8, 10, 12, 15, 20, 25]

FORBIDDEN_SQL_TOKENS = [
    "scanner_findings",
    "scanner_runs",
    "scanner_jobs",
    "excluded_cases",
    "downstream_signal",
    "final_label",
    "review_notes",
    "auto_tags",
]

SURFACES = [
    "source",
    "test",
    "dependency_manifest",
    "lockfile",
    "ci_workflow",
    "configuration",
    "script",
    "documentation",
    "generated_vendor",
    "other",
]

AGENT_TOOLS = ["codex", "copilot", "claude", "cursor", "devin"]


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
    parquet = path_base.with_suffix(".parquet")
    try:
        df.to_parquet(parquet, index=False)
        return str(parquet)
    except Exception as exc:
        pkl = path_base.with_suffix(".pkl")
        df.to_pickle(pkl)
        note = path_base.with_suffix(".parquet_unavailable.txt")
        note.write_text(str(exc), encoding="utf-8")
        return str(pkl)


def load_frame(path_base: Path) -> pd.DataFrame:
    pq = path_base.with_suffix(".parquet")
    pk = path_base.with_suffix(".pkl")
    if pq.exists():
        return pd.read_parquet(pq)
    if pk.exists():
        return pd.read_pickle(pk)
    raise FileNotFoundError(f"Neither {pq} nor {pk} exists")


def normalize_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def dt_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, utc=True, errors="coerce")


def entropy_from_counts(counts) -> float:
    a = np.asarray(list(counts), dtype=float)
    a = a[a > 0]
    if len(a) == 0:
        return 0.0
    p = a / a.sum()
    return float(-(p * np.log2(p)).sum())


def mad_series(s: pd.Series) -> float:
    x = pd.to_numeric(s, errors="coerce").dropna().to_numpy(dtype=float)
    if len(x) == 0:
        return float("nan")
    med = np.median(x)
    return float(np.median(np.abs(x - med)))


def safe_log1p_signed(x):
    if pd.isna(x):
        return np.nan
    x = float(x)
    return math.copysign(math.log1p(abs(x)), x)


def sql_guard(sql: str, log_path: Path) -> None:
    low = sql.lower()
    hits = [t for t in FORBIDDEN_SQL_TOKENS if t in low]
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{now_iso()}] {sql.strip()}\n")
    if hits:
        raise RuntimeError(f"FORBIDDEN_SQL_REFERENCE: {hits}")


def safe_query(con: sqlite3.Connection, sql: str, log_path: Path, params=()) -> pd.DataFrame:
    sql_guard(sql, log_path)
    return pd.read_sql_query(sql, con, params=params)


def table_exists(con: sqlite3.Connection, table: str, log_path: Path) -> bool:
    df = safe_query(
        con,
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        log_path,
        (table,),
    )
    return not df.empty


def table_columns(con: sqlite3.Connection, table: str, log_path: Path) -> list[str]:
    # PRAGMA is safe but log it explicitly.
    sql = f"PRAGMA table_info({table})"
    sql_guard(sql, log_path)
    rows = con.execute(sql).fetchall()
    return [str(r[1]) for r in rows]


def open_ro(db: Path) -> sqlite3.Connection:
    uri = f"file:{db.resolve()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def choose_cols(cols: list[str], wanted: list[str]) -> list[str]:
    s = set(cols)
    return [c for c in wanted if c in s]


def path_surface(path: str) -> str:
    p = str(path or "").replace("\\", "/").lower().strip()
    name = p.rsplit("/", 1)[-1]

    if any(x in p for x in ["/vendor/", "/vendors/", "/generated/", "/dist/", "/build/"]) or name.endswith(".min.js"):
        return "generated_vendor"

    if (
        p.startswith(".github/workflows/")
        or "/.github/workflows/" in p
        or name in {".gitlab-ci.yml", "jenkinsfile", "azure-pipelines.yml"}
        or "/.circleci/" in p
        or p.startswith(".circleci/")
    ):
        return "ci_workflow"

    lock_names = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "pnpm-lock.yml",
        "pipfile.lock", "poetry.lock", "cargo.lock", "go.sum", "composer.lock",
        "gemfile.lock", "packages.lock.json", "bun.lockb", "bun.lock",
    }
    if name in lock_names or name.endswith(".lock"):
        return "lockfile"

    manifest_names = {
        "package.json", "pyproject.toml", "pipfile", "requirements.txt",
        "go.mod", "cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts",
        "composer.json", "gemfile", "setup.py", "setup.cfg", "tox.ini",
        "environment.yml", "environment.yaml",
    }
    if name in manifest_names or re.match(r"requirements[-_.].*\.txt$", name):
        return "dependency_manifest"

    if (
        p.startswith("tests/") or "/tests/" in p or p.startswith("test/") or "/test/" in p
        or p.startswith("spec/") or "/spec/" in p or "/__tests__/" in p
        or re.search(r"(^|/)[^/]+\.(test|spec)\.[^.]+$", p)
        or re.search(r"(^|/)test_[^/]+\.[^.]+$", p)
    ):
        return "test"

    if (
        p.startswith("docs/") or "/docs/" in p or name.startswith("readme")
        or name.startswith("changelog") or name.endswith((".md", ".rst", ".adoc"))
    ):
        return "documentation"

    if (
        p.startswith("scripts/") or "/scripts/" in p or p.startswith("bin/") or "/bin/" in p
        or name.endswith((".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd"))
    ):
        return "script"

    config_names = {
        "dockerfile", "docker-compose.yml", "docker-compose.yaml", ".dockerignore",
        ".editorconfig", ".eslintrc", ".prettierrc", "tsconfig.json", "vite.config.js",
        "vite.config.ts", "webpack.config.js", "webpack.config.ts", "rollup.config.js",
        "babel.config.js", "next.config.js", "nuxt.config.ts", "eslint.config.js",
    }
    if (
        name in config_names
        or name.startswith(".env")
        or name.endswith((".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"))
        or "/config/" in p or p.startswith("config/")
    ):
        return "configuration"

    source_exts = {
        ".js", ".jsx", ".ts", ".tsx", ".py", ".java", ".go", ".rs", ".c", ".cc",
        ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".kts",
        ".scala", ".sh", ".sql", ".vue", ".svelte", ".dart", ".ex", ".exs",
    }
    ext = Path(name).suffix.lower()
    if ext in source_exts:
        return "source"

    return "other"


def extension_of(path: str) -> str:
    p = Path(str(path or ""))
    name = p.name.lower()
    if name in {"dockerfile", "makefile", "jenkinsfile", "gemfile", "pipfile"}:
        return name
    return p.suffix.lower() or "__NOEXT__"


def detect_tool_from_text(text: str) -> dict[str, int]:
    low = str(text or "").lower()
    return {f"has_{tool}_marker": int(tool in low) for tool in AGENT_TOOLS}


def detect_marker_source(text: str) -> dict[str, int]:
    low = str(text or "").lower()
    return {
        "marker_in_issue": int("issue" in low),
        "marker_in_pr_body": int("pr_body" in low or "pull" in low or "body" in low),
        "marker_in_branch": int("branch" in low or "head_ref" in low),
        "marker_in_author": int("author" in low or "bot" in low),
    }


def build_manifest(runroot: Path, db: Path, repo: Path) -> None:
    man = runroot / "00_manifest"
    man.mkdir(parents=True, exist_ok=True)
    write_json(man / "RUN_MANIFEST.json", {
        "method": "Full-Corpus Outcome-Blind Workflow Discovery v1.1",
        "created_at": now_iso(),
        "expected_cases": EXPECTED_CASES,
        "seed": SEED,
        "resamples": RESAMPLES,
        "repo_sample_fraction": REPO_SAMPLE_FRAC,
        "source_db": str(db.resolve()),
        "db_sha256": sha256_file(db),
        "repo": str(repo.resolve()),
        "forbidden_sql_tokens": FORBIDDEN_SQL_TOKENS,
    })
    (man / "DB_SHA256.txt").write_text(sha256_file(db) + "\n", encoding="utf-8")
    write_json(man / "FORBIDDEN_SOURCES.json", FORBIDDEN_SQL_TOKENS)
    write_json(man / "PATH_RULES_v1.json", {
        "surfaces": SURFACES,
        "implementation": "deterministic path_surface() in discovery.py",
    })


def stage_extract(runroot: Path, db: Path, repo: Path) -> None:
    actual_sha = sha256_file(db)
    if actual_sha != EXPECTED_DB_SHA256:
        raise RuntimeError(f"DB_SHA256_MISMATCH expected={EXPECTED_DB_SHA256} actual={actual_sha}")
    build_manifest(runroot, db, repo)
    log = runroot / "logs" / "sql_access.log"
    con = open_ro(db)

    required = ["cases", "repos", "issues", "pull_requests", "pr_files"]
    missing = [t for t in required if not table_exists(con, t, log)]
    if missing:
        raise RuntimeError(f"MISSING_REQUIRED_TABLES={missing}")

    schemas = {}
    for t in ["cases", "repos", "issues", "pull_requests", "pr_files", "ai_markers", "upstream_features", "issue_pr_links"]:
        if table_exists(con, t, log):
            schemas[t] = table_columns(con, t, log)
    write_json(runroot / "00_manifest" / "SCHEMA_SNAPSHOT.json", schemas)

    ccols = schemas["cases"]
    needed_case = ["id", "repo_id", "issue_id", "pr_id"]
    if not all(x in ccols for x in needed_case):
        raise RuntimeError(f"cases missing linkage columns: {needed_case}")

    rcols = schemas["repos"]
    icols = schemas["issues"]
    pcols = schemas["pull_requests"]

    select = [
        "c.id AS case_id", "c.repo_id", "c.issue_id", "c.pr_id",
    ]
    for col in choose_cols(rcols, ["full_name", "html_url", "stars", "language", "archived", "collected_at"]):
        select.append(f"r.{col} AS repo_{col}")
    for col in choose_cols(icols, ["number", "url", "title", "body", "author", "state", "labels", "comments_count", "created_at", "updated_at", "closed_at", "word_count", "is_english"]):
        select.append(f"i.{col} AS issue_{col}")
    for col in choose_cols(pcols, ["number", "url", "title", "body", "author", "state", "merged", "head_ref", "base_ref", "head_sha", "base_sha", "additions", "deletions", "changed_files_count", "commits_count", "review_comments_count", "created_at", "updated_at", "closed_at", "merged_at"]):
        select.append(f"p.{col} AS pr_{col}")

    sql = f"""
    SELECT {', '.join(select)}
    FROM cases c
    JOIN repos r ON r.id = c.repo_id
    JOIN issues i ON i.id = c.issue_id
    JOIN pull_requests p ON p.id = c.pr_id
    ORDER BY c.id
    """
    base = safe_query(con, sql, log)

    if len(base) != EXPECTED_CASES or base["case_id"].nunique() != EXPECTED_CASES:
        raise RuntimeError(f"CASE_INVARIANT_FAIL rows={len(base)} unique={base['case_id'].nunique()}")

    # Text is saved separately so it cannot accidentally dominate structured analyses.
    text_cols = [c for c in ["case_id", "repo_id", "issue_id", "pr_id", "issue_title", "issue_body", "pr_title", "pr_body"] if c in base.columns]
    save_frame(base[text_cols].copy(), runroot / "01_data" / "issue_pr_text")

    # Deterministic features.
    feat = base.copy()
    for c in ["issue_title", "issue_body", "pr_title", "pr_body"]:
        if c in feat.columns:
            feat[f"{c}_chars"] = feat[c].fillna("").astype(str).str.len()
            feat[f"{c}_words_auto"] = feat[c].fillna("").astype(str).str.findall(r"\b\w+\b").str.len()
            feat[f"{c}_lines"] = feat[c].fillna("").astype(str).str.count("\n") + 1

    if "issue_labels" in feat.columns:
        feat["issue_label_count"] = feat["issue_labels"].fillna("").astype(str).apply(
            lambda x: len([z for z in re.split(r"[,;|]", x) if z.strip()]) if x else 0
        )

    for src, dst in [
        ("issue_created_at", "issue_created_dt"),
        ("issue_closed_at", "issue_closed_dt"),
        ("pr_created_at", "pr_created_dt"),
        ("pr_merged_at", "pr_merged_dt"),
        ("pr_closed_at", "pr_closed_dt"),
    ]:
        if src in feat.columns:
            feat[dst] = dt_series(feat[src])

    if "issue_created_dt" in feat.columns and "pr_created_dt" in feat.columns:
        feat["issue_to_pr_hours"] = (feat["pr_created_dt"] - feat["issue_created_dt"]).dt.total_seconds() / 3600.0
    if "pr_created_dt" in feat.columns and "pr_merged_dt" in feat.columns:
        feat["pr_to_merge_hours"] = (feat["pr_merged_dt"] - feat["pr_created_dt"]).dt.total_seconds() / 3600.0
    if "issue_created_dt" in feat.columns and "issue_closed_dt" in feat.columns:
        feat["issue_open_hours"] = (feat["issue_closed_dt"] - feat["issue_created_dt"]).dt.total_seconds() / 3600.0
    if "pr_created_dt" in feat.columns and "pr_closed_dt" in feat.columns:
        feat["pr_open_hours"] = (feat["pr_closed_dt"] - feat["pr_created_dt"]).dt.total_seconds() / 3600.0

    for prefix in ["issue", "pr"]:
        dcol = f"{prefix}_created_dt"
        if dcol in feat.columns:
            feat[f"{prefix}_created_year"] = feat[dcol].dt.year
            feat[f"{prefix}_created_month"] = feat[dcol].dt.to_period("M").astype(str)
            feat[f"{prefix}_created_quarter"] = feat[dcol].dt.to_period("Q").astype(str)
            feat[f"{prefix}_created_weekday"] = feat[dcol].dt.weekday
            feat[f"{prefix}_created_hour"] = feat[dcol].dt.hour

    if "issue_author" in feat.columns and "pr_author" in feat.columns:
        ia = feat["issue_author"].fillna("").astype(str).str.lower().str.strip()
        pa = feat["pr_author"].fillna("").astype(str).str.lower().str.strip()
        feat["same_issue_pr_author"] = ((ia != "") & (ia == pa)).astype(int)

        issue_counts = ia[ia != ""].value_counts()
        pr_counts = pa[pa != ""].value_counts()
        feat["issue_author_case_count"] = ia.map(issue_counts).fillna(0).astype(int)
        feat["pr_author_case_count"] = pa.map(pr_counts).fillna(0).astype(int)

        issue_repo = feat.loc[ia != "", ["repo_id"]].copy()
        issue_repo["author_norm"] = ia[ia != ""].values
        issue_dist = issue_repo.groupby("author_norm")["repo_id"].nunique()
        pr_repo = feat.loc[pa != "", ["repo_id"]].copy()
        pr_repo["author_norm"] = pa[pa != ""].values
        pr_dist = pr_repo.groupby("author_norm")["repo_id"].nunique()
        feat["issue_author_distinct_repo_count"] = ia.map(issue_dist).fillna(0).astype(int)
        feat["pr_author_distinct_repo_count"] = pa.map(pr_dist).fillna(0).astype(int)

        # prior observed corpus activity based on issue timestamp ordering.
        feat["issue_author_prior_case_count_in_corpus"] = 0
        if "issue_created_dt" in feat.columns:
            tmp = feat[["case_id", "issue_author", "issue_created_dt"]].copy()
            tmp["author_norm"] = tmp["issue_author"].fillna("").astype(str).str.lower().str.strip()
            tmp = tmp.sort_values(["author_norm", "issue_created_dt", "case_id"])
            tmp["prior"] = tmp.groupby("author_norm").cumcount()
            prior_map = dict(zip(tmp["case_id"], tmp["prior"]))
            feat["issue_author_prior_case_count_in_corpus"] = feat["case_id"].map(prior_map).fillna(0).astype(int)

    for col in ["pr_additions", "pr_deletions", "pr_changed_files_count", "pr_commits_count", "pr_review_comments_count"]:
        if col in feat.columns:
            feat[col] = pd.to_numeric(feat[col], errors="coerce")
    if "pr_additions" in feat.columns and "pr_deletions" in feat.columns:
        feat["pr_total_changed_lines"] = feat["pr_additions"].fillna(0) + feat["pr_deletions"].fillna(0)
        feat["add_delete_ratio"] = np.where(feat["pr_deletions"] > 0, feat["pr_additions"] / feat["pr_deletions"], np.nan)
    if "pr_total_changed_lines" in feat.columns and "pr_changed_files_count" in feat.columns:
        feat["changed_lines_per_file"] = np.where(feat["pr_changed_files_count"] > 0, feat["pr_total_changed_lines"] / feat["pr_changed_files_count"], np.nan)
    if "pr_total_changed_lines" in feat.columns and "pr_commits_count" in feat.columns:
        feat["changed_lines_per_commit"] = np.where(feat["pr_commits_count"] > 0, feat["pr_total_changed_lines"] / feat["pr_commits_count"], np.nan)
    if "pr_changed_files_count" in feat.columns and "pr_commits_count" in feat.columns:
        feat["files_per_commit"] = np.where(feat["pr_commits_count"] > 0, feat["pr_changed_files_count"] / feat["pr_commits_count"], np.nan)
    if "pr_review_comments_count" in feat.columns:
        feat["review_activity_present"] = (feat["pr_review_comments_count"].fillna(0) > 0).astype(int)

    # PR files.
    fcols = schemas["pr_files"]
    fsel = choose_cols(fcols, ["id", "pr_id", "filename", "status", "additions", "deletions"])
    files = safe_query(con, f"SELECT {', '.join(fsel)} FROM pr_files", log)
    files["surface"] = files["filename"].map(path_surface)
    files["extension"] = files["filename"].map(extension_of)
    write_csv(files, runroot / "01_data" / "changed_files.csv")

    agg_rows = []
    for pr_id, g in files.groupby("pr_id", sort=False):
        row = {"pr_id": pr_id, "pr_file_rows": len(g)}
        counts = g["surface"].value_counts().to_dict()
        for s in SURFACES:
            n = int(counts.get(s, 0))
            row[f"touches_{s}"] = int(n > 0)
            row[f"{s}_file_count"] = n
            row[f"{s}_file_fraction"] = n / len(g) if len(g) else 0.0
        row["num_distinct_change_surfaces"] = int(g["surface"].nunique())
        ex = g["extension"].value_counts()
        row["num_distinct_extensions"] = int(len(ex))
        row["dominant_extension"] = str(ex.index[0]) if len(ex) else ""
        row["extension_entropy"] = entropy_from_counts(ex.values)
        agg_rows.append(row)
    file_agg = pd.DataFrame(agg_rows)
    feat = feat.merge(file_agg, on="pr_id", how="left")
    for c in [x for x in feat.columns if x.startswith("touches_") or x.endswith("_file_count") or x.endswith("_file_fraction")]:
        if c in feat.columns:
            feat[c] = feat[c].fillna(0)

    # Agent markers: aggregate factual text only.
    if "ai_markers" in schemas:
        acols = schemas["ai_markers"]
        # Only read ai_markers; this table is on the explicit factual allowlist.
        markers = safe_query(con, "SELECT * FROM ai_markers", log)
        fk = "case_id" if "case_id" in markers.columns else ("pr_id" if "pr_id" in markers.columns else None)
        if fk:
            id_like = {"id", "case_id", "pr_id", "issue_id", "repo_id", "created_at", "updated_at"}
            text_cols2 = [c for c in markers.columns if c not in id_like]
            mrows = []
            for key, g in markers.groupby(fk, sort=False):
                texts = []
                for c in text_cols2:
                    texts.extend(g[c].dropna().astype(str).tolist())
                joined = " | ".join(texts)
                row = {fk: key, "agent_marker_count": len(g)}
                row.update(detect_tool_from_text(joined))
                row.update(detect_marker_source(joined))
                row["distinct_marker_tool_count"] = sum(row[f"has_{t}_marker"] for t in AGENT_TOOLS)
                mrows.append(row)
            magg = pd.DataFrame(mrows)
            feat = feat.merge(magg, on=fk, how="left")
            for c in [x for x in feat.columns if x.startswith("has_") or x.startswith("marker_in_") or x in {"agent_marker_count", "distinct_marker_tool_count"}]:
                feat[c] = feat[c].fillna(0).astype(int)

    # Automatic factual upstream features from strict allowlist / aliases only.
    selected_upstream = []
    if "upstream_features" in schemas:
        ucols = schemas["upstream_features"]
        norm = {normalize_name(c): c for c in ucols}
        aliases = {
            "has_code_block": ["has_code_block", "contains_code_block", "code_block_present"],
            "code_block_count": ["code_block_count", "num_code_blocks"],
            "has_inline_code": ["has_inline_code", "contains_inline_code"],
            "inline_code_count": ["inline_code_count", "num_inline_code"],
            "has_traceback_or_log": ["has_traceback_or_log", "has_traceback", "contains_traceback", "has_log", "contains_log"],
            "has_dependency_or_version_mention": ["has_dependency_or_version_mention", "has_version_mention", "contains_version", "dependency_version_mention"],
            "has_suggested_fix": ["has_suggested_fix", "suggested_fix", "contains_suggested_fix"],
            "has_reproduction_steps": ["has_reproduction_steps", "reproduction_steps", "contains_reproduction_steps"],
            "url_count": ["url_count", "num_urls"],
        }
        chosen = {}
        for outcol, als in aliases.items():
            for a in als:
                if a in norm:
                    chosen[outcol] = norm[a]
                    break
        fk = "case_id" if "case_id" in ucols else ("issue_id" if "issue_id" in ucols else None)
        if fk and chosen:
            qcols = [fk] + sorted(set(chosen.values()))
            udf = safe_query(con, f"SELECT {', '.join(qcols)} FROM upstream_features", log)
            rename = {v: k for k, v in chosen.items()}
            udf = udf.rename(columns=rename)
            feat = feat.merge(udf, on=fk, how="left")
            selected_upstream = rename
    write_json(runroot / "00_manifest" / "UPSTREAM_FEATURE_ALLOWLIST_USED.json", selected_upstream)

    # Repository case count.
    feat["repo_case_count_in_corpus"] = feat["repo_id"].map(feat["repo_id"].value_counts()).astype(int)

    # Analytical transformed copies.
    transform_cols = [
        "pr_additions", "pr_deletions", "pr_total_changed_lines", "pr_changed_files_count",
        "pr_commits_count", "pr_review_comments_count", "repo_stars", "issue_comments_count",
        "issue_author_case_count", "pr_author_case_count", "repo_case_count_in_corpus",
    ]
    for c in transform_cols:
        if c in feat.columns:
            feat[f"log1p_{c}"] = pd.to_numeric(feat[c], errors="coerce").apply(lambda x: np.log1p(x) if pd.notna(x) and x >= 0 else np.nan)
    for c in ["issue_to_pr_hours", "pr_to_merge_hours", "issue_open_hours", "pr_open_hours"]:
        if c in feat.columns:
            feat[f"signed_log1p_{c}"] = pd.to_numeric(feat[c], errors="coerce").apply(safe_log1p_signed)

    # Remove raw text from structured feature store.
    drop_text = [c for c in ["issue_title", "issue_body", "pr_title", "pr_body"] if c in feat.columns]
    structured = feat.drop(columns=drop_text)
    # pandas Period conversion may have produced weird object values; all saved as strings already.
    save_frame(structured, runroot / "01_data" / "workflow_features")

    # Optional graph edge export.
    if "issue_pr_links" in schemas:
        lcols = schemas["issue_pr_links"]
        if "issue_id" in lcols and "pr_id" in lcols:
            ldf = safe_query(con, "SELECT issue_id, pr_id FROM issue_pr_links", log)
            write_csv(ldf.drop_duplicates(), runroot / "01_data" / "issue_pr_links.csv")

    con.close()

    feature_dict = []
    for c in structured.columns:
        feature_dict.append({
            "feature": c,
            "dtype": str(structured[c].dtype),
            "source": "deterministic extraction/derivation",
            "security_outcome_used": "NO",
        })
    write_csv(pd.DataFrame(feature_dict), runroot / "00_manifest" / "FEATURE_DICTIONARY.csv")

    write_json(runroot / "00_manifest" / "EXTRACT_SUMMARY.json", {
        "rows": int(len(structured)),
        "unique_cases": int(structured["case_id"].nunique()),
        "repositories": int(structured["repo_id"].nunique()),
        "columns": int(len(structured.columns)),
        "created_at": now_iso(),
    })


def stage_quality(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "02_quality"
    out.mkdir(parents=True, exist_ok=True)

    invariants = {
        "rows": int(len(df)),
        "unique_case_ids": int(df["case_id"].nunique()),
        "repositories": int(df["repo_id"].nunique()),
        "expected_cases": EXPECTED_CASES,
        "case_count_pass": bool(len(df) == EXPECTED_CASES and df["case_id"].nunique() == EXPECTED_CASES),
    }
    write_json(out / "invariants.json", invariants)
    if not invariants["case_count_pass"]:
        raise RuntimeError(f"QUALITY_INVARIANT_FAIL={invariants}")

    miss = pd.DataFrame({
        "feature": df.columns,
        "missing_count": [int(df[c].isna().sum()) for c in df.columns],
        "missing_percent": [float(df[c].isna().mean() * 100) for c in df.columns],
    }).sort_values(["missing_percent", "feature"], ascending=[False, True])
    write_csv(miss, out / "missingness.csv")

    dup = df[df.duplicated("case_id", keep=False)].sort_values("case_id")
    write_csv(dup, out / "duplicate_audit.csv")

    flags = []
    for c in ["issue_to_pr_hours", "pr_to_merge_hours", "issue_open_hours", "pr_open_hours"]:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            for idx in df.index[s < 0]:
                flags.append({"case_id": df.at[idx, "case_id"], "flag": f"negative_{c}", "value": df.at[idx, c]})
    if "pr_total_changed_lines" in df.columns:
        s = pd.to_numeric(df["pr_total_changed_lines"], errors="coerce")
        for idx in df.index[s == 0]:
            flags.append({"case_id": df.at[idx, "case_id"], "flag": "zero_changed_lines", "value": 0})

    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in {"case_id", "repo_id", "issue_id", "pr_id"}]
    extreme_rows = []
    for c in numeric_cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) < 20 or s.nunique() < 5:
            continue
        lo, hi = s.quantile([0.005, 0.995])
        mask = pd.to_numeric(df[c], errors="coerce").lt(lo) | pd.to_numeric(df[c], errors="coerce").gt(hi)
        for idx in df.index[mask]:
            extreme_rows.append({"case_id": df.at[idx, "case_id"], "feature": c, "value": df.at[idx, c], "p005": lo, "p995": hi})
    write_csv(pd.DataFrame(extreme_rows), out / "extreme_values.csv")
    write_csv(pd.DataFrame(flags), out / "data_quality_flags.csv")


def numeric_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c in df.select_dtypes(include=[np.number]).columns:
        if c in {"case_id", "repo_id", "issue_id", "pr_id"}:
            continue
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if len(s) == 0:
            continue
        q = s.quantile([0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
        rows.append({
            "feature": c,
            "N": int(len(s)),
            "missing": int(df[c].isna().sum()),
            "mean": float(s.mean()),
            "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
            "min": float(s.min()),
            "p01": float(q.loc[0.01]), "p05": float(q.loc[0.05]), "p10": float(q.loc[0.10]),
            "p25": float(q.loc[0.25]), "median": float(q.loc[0.50]), "p75": float(q.loc[0.75]),
            "p90": float(q.loc[0.90]), "p95": float(q.loc[0.95]), "p99": float(q.loc[0.99]),
            "max": float(s.max()),
            "IQR": float(q.loc[0.75] - q.loc[0.25]),
            "MAD": mad_series(s),
            "skewness": float(stats.skew(s, bias=False, nan_policy="omit")) if len(s) > 2 else np.nan,
            "kurtosis": float(stats.kurtosis(s, bias=False, nan_policy="omit")) if len(s) > 3 else np.nan,
        })
    return pd.DataFrame(rows)


def stage_landscape(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "03_landscape"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(numeric_profile(df), out / "numeric_profile.csv")

    rows = []
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]):
            # Keep low-cardinality/binary numeric categoricals.
            if df[c].nunique(dropna=True) > 20:
                continue
        else:
            if c.endswith("_dt") or c in {"repo_full_name", "repo_html_url", "issue_url", "pr_url", "issue_author", "pr_author", "pr_head_sha", "pr_base_sha"}:
                continue
            if df[c].nunique(dropna=True) > 100:
                continue
        vc = df[c].fillna("__MISSING__").astype(str).value_counts(dropna=False)
        ent = entropy_from_counts(vc.values)
        for val, cnt in vc.items():
            rows.append({"feature": c, "value": val, "count": int(cnt), "percent": float(cnt / len(df) * 100), "feature_entropy": ent})
    write_csv(pd.DataFrame(rows), out / "categorical_profile.csv")

    surf_rows = []
    for s in SURFACES:
        c = f"touches_{s}"
        if c in df.columns:
            surf_rows.append({"surface": s, "cases": int(df[c].fillna(0).astype(int).sum()), "percent": float(df[c].fillna(0).mean() * 100)})
    write_csv(pd.DataFrame(surf_rows), out / "file_surface_profile.csv")

    agent_rows = []
    for t in AGENT_TOOLS:
        c = f"has_{t}_marker"
        if c in df.columns:
            agent_rows.append({"tool_marker": t, "cases": int(df[c].sum()), "percent": float(df[c].mean() * 100), "repositories": int(df.loc[df[c] == 1, "repo_id"].nunique())})
    write_csv(pd.DataFrame(agent_rows), out / "agent_marker_profile.csv")


def core_signature_from_row(row: pd.Series) -> str:
    items = [s for s in SURFACES if int(row.get(f"touches_{s}", 0) or 0) == 1]
    return "{" + ",".join(items) + "}" if items else "{}"


def stage_signatures(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "04_signatures"
    out.mkdir(parents=True, exist_ok=True)
    work = df[["case_id", "repo_id"]].copy()
    work["core_signature"] = df.apply(core_signature_from_row, axis=1)

    ext = []
    for _, r in df.iterrows():
        items = [s for s in SURFACES if int(r.get(f"touches_{s}", 0) or 0) == 1]
        if "same_issue_pr_author" in df.columns:
            items.append("same_author" if int(r.get("same_issue_pr_author", 0) or 0) else "different_author")
        if "review_activity_present" in df.columns:
            items.append("reviewed" if int(r.get("review_activity_present", 0) or 0) else "no_review_activity")
        for t in AGENT_TOOLS:
            if int(r.get(f"has_{t}_marker", 0) or 0):
                items.append(f"agent_{t}")
        ext.append("{" + ",".join(sorted(items)) + "}")
    work["extended_signature"] = ext
    write_csv(work, out / "workflow_signatures.csv")

    date_col = "issue_created_dt" if "issue_created_dt" in df.columns else None
    rows = []
    merged = work.join(df.set_index("case_id")[[c for c in ["issue_created_dt"] if c in df.columns]], on="case_id")
    for typ in ["core_signature", "extended_signature"]:
        for sig, g in merged.groupby(typ):
            row = {
                "signature_type": typ,
                "signature": sig,
                "case_count": len(g),
                "support": len(g) / len(df),
                "repository_count": g["repo_id"].nunique(),
                "repository_coverage": g["repo_id"].nunique() / df["repo_id"].nunique(),
            }
            if date_col and date_col in g.columns:
                dt = pd.to_datetime(g[date_col], utc=True, errors="coerce")
                row["first_seen"] = dt.min()
                row["last_seen"] = dt.max()
            rows.append(row)
    result = pd.DataFrame(rows).sort_values(["signature_type", "case_count"], ascending=[True, False])
    write_csv(result, out / "ranked_signatures.csv")

    # Repository-blocked support stability for core signatures.
    core_sigs = result.loc[result["signature_type"] == "core_signature", "signature"].tolist()
    repos = np.array(sorted(df["repo_id"].dropna().unique()))
    rng = np.random.default_rng(SEED)
    records = {sig: [] for sig in core_sigs}
    workmap = work.set_index("case_id")
    for _ in range(RESAMPLES):
        chosen = set(rng.choice(repos, size=max(1, int(len(repos) * REPO_SAMPLE_FRAC)), replace=False).tolist())
        ids = df.loc[df["repo_id"].isin(chosen), "case_id"]
        sub = workmap.loc[workmap.index.intersection(ids)]
        vc = sub["core_signature"].value_counts(normalize=True)
        for sig in core_sigs:
            records[sig].append(float(vc.get(sig, 0.0)))
    st = []
    for sig, vals in records.items():
        arr = np.asarray(vals)
        st.append({
            "signature": sig,
            "median_support": float(np.median(arr)),
            "p025_support": float(np.quantile(arr, 0.025)),
            "p975_support": float(np.quantile(arr, 0.975)),
            "presence_fraction": float(np.mean(arr > 0)),
        })
    write_csv(pd.DataFrame(st), out / "signature_stability.csv")


def item_binary_columns(df: pd.DataFrame) -> list[str]:
    # Frozen interpretable item universe: change surfaces + simple process + tool markers
    # + a small allowlist of automatically derived issue-structure facts.
    wanted = (
        [f"touches_{s}" for s in SURFACES]
        + ["same_issue_pr_author", "review_activity_present"]
        + [f"has_{t}_marker" for t in AGENT_TOOLS]
        + [
            "has_code_block", "has_inline_code", "has_traceback_or_log",
            "has_dependency_or_version_mention", "has_suggested_fix",
            "has_reproduction_steps",
        ]
    )
    cols = []
    for c in wanted:
        if c not in df.columns:
            continue
        vals = set(pd.to_numeric(df[c], errors="coerce").dropna().unique().tolist())
        if vals and vals.issubset({0, 1}):
            cols.append(c)
    return cols


def combo_support(X: np.ndarray, idxs: tuple[int, ...]) -> float:
    if len(idxs) == 1:
        return float(X[:, idxs[0]].mean())
    return float(np.all(X[:, idxs] == 1, axis=1).mean())


def mine_itemsets(df: pd.DataFrame, min_support: float, max_len: int = 5):
    cols = item_binary_columns(df)
    X = df[cols].fillna(0).astype(int).to_numpy()
    frequent = {}
    # Apriori-style candidate extension, deterministic and dependency-free.
    prev = []
    for i, c in enumerate(cols):
        sup = float(X[:, i].mean())
        if sup >= min_support:
            key = (i,)
            frequent[key] = sup
            prev.append(key)
    for k in range(2, max_len + 1):
        if not prev:
            break
        candidates = set()
        prev_set = set(prev)
        for a_i in range(len(prev)):
            for b_i in range(a_i + 1, len(prev)):
                a, b = prev[a_i], prev[b_i]
                u = tuple(sorted(set(a) | set(b)))
                if len(u) != k:
                    continue
                if all(tuple(x for x in u if x != drop) in prev_set for drop in u):
                    candidates.add(u)
        curr = []
        for cand in sorted(candidates):
            sup = combo_support(X, cand)
            if sup >= min_support:
                frequent[cand] = sup
                curr.append(cand)
        prev = curr
    rows = []
    for idxs, sup in frequent.items():
        items = tuple(cols[i] for i in idxs)
        mask = np.all(X[:, idxs] == 1, axis=1)
        rows.append({
            "items": "|".join(items),
            "length": len(items),
            "support": sup,
            "case_count": int(mask.sum()),
            "repository_count": int(df.loc[mask, "repo_id"].nunique()),
        })
    return pd.DataFrame(rows), frequent, cols, X


def stage_patterns(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "05_patterns"
    out.mkdir(parents=True, exist_ok=True)

    all_runs = []
    primary_frequent = None
    primary_cols = None
    primary_X = None
    for ms in [0.01, 0.02, 0.05]:
        itemdf, frequent, cols, X = mine_itemsets(df, ms, 5)
        itemdf["min_support_setting"] = ms
        all_runs.append(itemdf)
        if abs(ms - 0.02) < 1e-9:
            primary_frequent, primary_cols, primary_X = frequent, cols, X
    all_itemsets = pd.concat(all_runs, ignore_index=True) if all_runs else pd.DataFrame()
    write_csv(all_itemsets, out / "frequent_itemsets.csv")

    # Association rules from primary itemsets. Frozen minimum confidence 0.30.
    rules = []
    if primary_frequent:
        name_to_idx = {c: i for i, c in enumerate(primary_cols)}
        supp_by_names = {tuple(primary_cols[i] for i in idxs): sup for idxs, sup in primary_frequent.items()}
        for item_names, sup_all in list(supp_by_names.items()):
            if len(item_names) < 2:
                continue
            items = tuple(item_names)
            for r in range(1, len(items)):
                for ant in itertools.combinations(items, r):
                    cons = tuple(x for x in items if x not in ant)
                    ant_sup = supp_by_names.get(tuple(sorted(ant, key=lambda x: name_to_idx[x])))
                    cons_sup = supp_by_names.get(tuple(sorted(cons, key=lambda x: name_to_idx[x])))
                    if not ant_sup or not cons_sup:
                        continue
                    conf = sup_all / ant_sup
                    if conf < 0.30:
                        continue
                    lift = conf / cons_sup if cons_sup > 0 else np.nan
                    leverage = sup_all - ant_sup * cons_sup
                    conviction = (1 - cons_sup) / (1 - conf) if conf < 1 else np.inf
                    rules.append({
                        "antecedent": "|".join(ant),
                        "consequent": "|".join(cons),
                        "support": sup_all,
                        "confidence": conf,
                        "lift": lift,
                        "leverage": leverage,
                        "conviction": conviction,
                    })
    rdf = pd.DataFrame(rules)
    if not rdf.empty:
        rdf = rdf.sort_values(["lift", "support"], ascending=[False, False])
    write_csv(rdf, out / "association_rules.csv")

    # Stability of all primary itemsets under repository-blocked resampling.
    # Compute per-repository itemset counts once, then resampling is just matrix sums.
    if primary_frequent:
        repos = np.array(sorted(df["repo_id"].dropna().unique()))
        repo_to_code = {r:i for i,r in enumerate(repos)}
        repo_codes = df["repo_id"].map(repo_to_code).to_numpy(int)
        repo_sizes = np.bincount(repo_codes, minlength=len(repos)).astype(float)
        item_keys = list(primary_frequent.keys())
        item_names = {idxs: tuple(primary_cols[i] for i in idxs) for idxs in item_keys}
        counts_mat = np.zeros((len(item_keys), len(repos)), dtype=np.int32)
        for row_i, idxs in enumerate(item_keys):
            mask = np.all(primary_X[:, idxs] == 1, axis=1)
            counts_mat[row_i] = np.bincount(repo_codes[mask], minlength=len(repos))
        rng = np.random.default_rng(SEED + 11)
        supports = np.zeros((len(item_keys), RESAMPLES), dtype=np.float32)
        choose_n = max(1, int(len(repos) * REPO_SAMPLE_FRAC))
        for j in range(RESAMPLES):
            chosen_idx = rng.choice(len(repos), size=choose_n, replace=False)
            den = repo_sizes[chosen_idx].sum()
            supports[:, j] = counts_mat[:, chosen_idx].sum(axis=1) / den if den > 0 else 0.0
        rows = []
        for row_i, idxs in enumerate(item_keys):
            arr = supports[row_i]
            full_sup = primary_frequent[idxs]
            rows.append({
                "items": "|".join(item_names[idxs]),
                "full_support": full_sup,
                "median_support": float(np.median(arr)),
                "p025_support": float(np.quantile(arr, 0.025)),
                "p975_support": float(np.quantile(arr, 0.975)),
                "rediscovered_fraction_at_2pct": float(np.mean(arr >= 0.02)),
            })
        write_csv(pd.DataFrame(rows), out / "pattern_stability.csv")


def stage_topology(runroot: Path) -> None:
    out = runroot / "06_topology"
    out.mkdir(parents=True, exist_ok=True)
    edge_path = runroot / "01_data" / "issue_pr_links.csv"
    if not edge_path.exists():
        write_json(out / "STATUS.json", {"status": "SKIPPED", "reason": "issue_pr_links edge export unavailable"})
        return
    edges = pd.read_csv(edge_path).dropna().drop_duplicates()
    if edges.empty:
        write_json(out / "STATUS.json", {"status": "SKIPPED", "reason": "no edges"})
        return

    adj = defaultdict(set)
    issue_deg = Counter()
    pr_deg = Counter()
    for r in edges.itertuples(index=False):
        i = f"I:{int(r.issue_id)}"
        p = f"P:{int(r.pr_id)}"
        adj[i].add(p); adj[p].add(i)
        issue_deg[int(r.issue_id)] += 1
        pr_deg[int(r.pr_id)] += 1
    write_csv(pd.DataFrame([{"issue_id": k, "degree": v} for k, v in issue_deg.items()]), out / "issue_degree.csv")
    write_csv(pd.DataFrame([{"pr_id": k, "degree": v} for k, v in pr_deg.items()]), out / "pr_degree.csv")

    seen = set(); comps = []
    for node in adj:
        if node in seen:
            continue
        stack = [node]; seen.add(node); nodes = []
        while stack:
            cur = stack.pop(); nodes.append(cur)
            for nb in adj[cur]:
                if nb not in seen:
                    seen.add(nb); stack.append(nb)
        ni = sum(x.startswith("I:") for x in nodes)
        np_ = sum(x.startswith("P:") for x in nodes)
        if ni == 1 and np_ == 1:
            topo = "1_issue_1_pr"
        elif ni == 1 and np_ > 1:
            topo = "1_issue_many_pr"
        elif ni > 1 and np_ == 1:
            topo = "many_issue_1_pr"
        else:
            topo = "multi_issue_multi_pr"
        comps.append({"component_id": len(comps) + 1, "nodes": len(nodes), "issue_count": ni, "pr_count": np_, "topology": topo})
    cdf = pd.DataFrame(comps)
    write_csv(cdf, out / "component_summary.csv")
    freq = cdf.groupby("topology").agg(components=("component_id", "count"), nodes=("nodes", "sum")).reset_index()
    write_csv(freq, out / "topology_frequency.csv")
    write_json(out / "graph_summary.json", {"edges": len(edges), "issues": len(issue_deg), "prs": len(pr_deg), "components": len(cdf)})


def cramers_v_bias_corrected(x, y) -> float:
    tab = pd.crosstab(pd.Series(x), pd.Series(y))
    if tab.empty or min(tab.shape) < 2:
        return np.nan
    chi2 = stats.chi2_contingency(tab, correction=False)[0]
    n = tab.to_numpy().sum()
    phi2 = chi2 / n
    r, k = tab.shape
    phi2corr = max(0, phi2 - ((k - 1) * (r - 1)) / max(n - 1, 1))
    rcorr = r - ((r - 1) ** 2) / max(n - 1, 1)
    kcorr = k - ((k - 1) ** 2) / max(n - 1, 1)
    den = min(kcorr - 1, rcorr - 1)
    return math.sqrt(phi2corr / den) if den > 0 else np.nan


def phi_binary(x, y) -> float:
    a = pd.to_numeric(pd.Series(x), errors="coerce")
    b = pd.to_numeric(pd.Series(y), errors="coerce")
    m = a.notna() & b.notna()
    if m.sum() < 3 or a[m].nunique() < 2 or b[m].nunique() < 2:
        return np.nan
    return float(np.corrcoef(a[m], b[m])[0, 1])


def stage_relationships(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "07_relationships"
    out.mkdir(parents=True, exist_ok=True)

    numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c not in {"case_id", "repo_id", "issue_id", "pr_id"} and df[c].nunique(dropna=True) > 2]
    # Reduce to <=60 most complete numeric vars to prevent unreadable O(p^2) explosion.
    numeric = sorted(numeric, key=lambda c: df[c].notna().mean(), reverse=True)[:60]
    sp = []
    for i, a in enumerate(numeric):
        for b in numeric[i+1:]:
            x = pd.to_numeric(df[a], errors="coerce")
            y = pd.to_numeric(df[b], errors="coerce")
            m = x.notna() & y.notna()
            if m.sum() < 30 or x[m].nunique() < 3 or y[m].nunique() < 3:
                continue
            rho, p = stats.spearmanr(x[m], y[m])
            sp.append({"a": a, "b": b, "n": int(m.sum()), "spearman_rho": float(rho), "p_value": float(p)})
    spdf = pd.DataFrame(sp)
    if not spdf.empty:
        spdf["abs_effect"] = spdf["spearman_rho"].abs()
        spdf = spdf.sort_values("abs_effect", ascending=False)
    write_csv(spdf, out / "spearman.csv")

    binary = []
    for c in df.columns:
        vals = set(pd.to_numeric(df[c], errors="coerce").dropna().unique().tolist()) if pd.api.types.is_numeric_dtype(df[c]) else set()
        if vals and vals.issubset({0,1}) and len(vals) == 2:
            binary.append(c)
    ph = []
    for i, a in enumerate(binary):
        for b in binary[i+1:]:
            val = phi_binary(df[a], df[b])
            ph.append({"a": a, "b": b, "phi": val, "abs_effect": abs(val) if pd.notna(val) else np.nan})
    phdf = pd.DataFrame(ph).sort_values("abs_effect", ascending=False) if ph else pd.DataFrame()
    write_csv(phdf, out / "phi.csv")

    categorical = []
    for c in df.columns:
        if c in {"case_id", "repo_id", "issue_id", "pr_id", "repo_full_name", "issue_author", "pr_author"}:
            continue
        nuniq = df[c].nunique(dropna=True)
        if 2 <= nuniq <= 20:
            categorical.append(c)
    cv = []
    for i, a in enumerate(categorical):
        for b in categorical[i+1:]:
            val = cramers_v_bias_corrected(df[a].fillna("__MISSING__"), df[b].fillna("__MISSING__"))
            cv.append({"a": a, "b": b, "cramers_v": val, "abs_effect": val})
    cvdf = pd.DataFrame(cv).sort_values("abs_effect", ascending=False) if cv else pd.DataFrame()
    write_csv(cvdf, out / "cramers_v.csv")

    # General MI on discretized / low-cardinality features; normalized only by saving entropies separately.
    mi_features = []
    encoded = {}
    for c in df.columns:
        if c in {"case_id", "repo_id", "issue_id", "pr_id", "repo_full_name", "issue_author", "pr_author", "issue_url", "pr_url"} or c.endswith("_dt"):
            continue
        s = df[c]
        if pd.api.types.is_numeric_dtype(s) and s.nunique(dropna=True) > 20:
            try:
                enc = pd.qcut(pd.to_numeric(s, errors="coerce"), q=10, duplicates="drop").astype(str).fillna("__MISSING__")
            except Exception:
                continue
        else:
            if s.nunique(dropna=True) > 50:
                continue
            enc = s.fillna("__MISSING__").astype(str)
        mi_features.append(c)
        encoded[c] = pd.factorize(enc)[0]
    mi_features = mi_features[:50]
    mirows = []
    for i, a in enumerate(mi_features):
        for b in mi_features[i+1:]:
            mi = mutual_info_score(encoded[a], encoded[b])
            mirows.append({"a": a, "b": b, "mutual_information": float(mi)})
    midf = pd.DataFrame(mirows).sort_values("mutual_information", ascending=False) if mirows else pd.DataFrame()
    write_csv(midf, out / "mutual_information.csv")

    # Stability for top 100 Spearman and top 100 phi pairs, repository-blocked.
    candidates = []
    if not spdf.empty:
        for r in spdf.head(100).itertuples(index=False):
            candidates.append(("spearman", r.a, r.b, r.spearman_rho))
    if not phdf.empty:
        for r in phdf.head(100).itertuples(index=False):
            candidates.append(("phi", r.a, r.b, r.phi))
    repos = np.array(sorted(df["repo_id"].dropna().unique()))
    rng = np.random.default_rng(SEED + 22)
    vals = {c[:3]: [] for c in candidates}
    for _ in range(RESAMPLES):
        chosen = set(rng.choice(repos, size=max(1, int(len(repos) * REPO_SAMPLE_FRAC)), replace=False).tolist())
        sub = df[df["repo_id"].isin(chosen)]
        for typ, a, b, full in candidates:
            if typ == "spearman":
                x = pd.to_numeric(sub[a], errors="coerce"); y = pd.to_numeric(sub[b], errors="coerce")
                m = x.notna() & y.notna()
                v = stats.spearmanr(x[m], y[m]).statistic if m.sum() >= 30 else np.nan
            else:
                v = phi_binary(sub[a], sub[b])
            vals[(typ,a,b)].append(v)
    strows = []
    for typ,a,b,full in candidates:
        arr = np.asarray(vals[(typ,a,b)], dtype=float)
        arr = arr[np.isfinite(arr)]
        if len(arr) == 0:
            continue
        strows.append({
            "type": typ, "a": a, "b": b, "full_effect": full,
            "median_effect": float(np.median(arr)),
            "p025_effect": float(np.quantile(arr, 0.025)),
            "p975_effect": float(np.quantile(arr, 0.975)),
            "sign_consistency": float(np.mean(np.sign(arr) == np.sign(full))) if full != 0 else np.nan,
        })
    write_csv(pd.DataFrame(strows), out / "relationship_stability.csv")


def stage_repository(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "08_repository"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for repo_id, g in df.groupby("repo_id"):
        row = {
            "repo_id": repo_id,
            "repo_full_name": g["repo_full_name"].iloc[0] if "repo_full_name" in g.columns else "",
            "case_count": len(g),
        }
        for c in ["pr_total_changed_lines", "pr_changed_files_count", "pr_commits_count", "issue_to_pr_hours", "pr_to_merge_hours", "issue_body_words_auto"]:
            if c in g.columns:
                row[f"median_{c}"] = pd.to_numeric(g[c], errors="coerce").median()
        for c in ["same_issue_pr_author", "review_activity_present"] + [f"touches_{s}" for s in SURFACES] + [f"has_{t}_marker" for t in AGENT_TOOLS]:
            if c in g.columns:
                row[f"rate_{c}"] = pd.to_numeric(g[c], errors="coerce").mean()
        rows.append(row)
    rdf = pd.DataFrame(rows)
    write_csv(rdf, out / "repository_profiles.csv")
    save_frame(rdf, runroot / "01_data" / "repository_profiles")

    eligible = rdf[rdf["case_count"] >= 5].copy()
    num = [c for c in eligible.select_dtypes(include=[np.number]).columns if c not in {"repo_id", "case_count"}]
    if len(eligible) < 10 or len(num) < 2:
        write_json(out / "repository_regime_status.json", {"status":"SKIPPED", "reason":"insufficient eligible repos/features"})
        return
    X = eligible[num].copy()
    X = X.fillna(X.median(numeric_only=True))
    Xs = RobustScaler().fit_transform(X)
    # Simple regime baseline: choose k 2..min(8,n-1) by silhouette.
    models = []
    best = None
    for k in range(2, min(8, len(eligible)-1) + 1):
        lab = KMeans(n_clusters=k, n_init=50, random_state=SEED).fit_predict(Xs)
        if len(set(lab)) < 2:
            continue
        sil = silhouette_score(Xs, lab)
        models.append({"k": k, "silhouette": sil})
        if best is None or sil > best[0]:
            best = (sil, k, lab)
    write_csv(pd.DataFrame(models), out / "repository_regime_models.csv")
    if best:
        eligible["repository_regime"] = best[2]
        write_csv(eligible[["repo_id", "repo_full_name", "case_count", "repository_regime"]], out / "repository_regimes.csv")


def aggregate_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    dt = pd.to_datetime(df["issue_created_dt"], utc=True, errors="coerce")
    key = dt.dt.to_period(period).astype(str)
    tmp = df.copy(); tmp["period"] = key
    rows = []
    for p, g in tmp.dropna(subset=["period"]).groupby("period"):
        row = {"period": p, "case_count": len(g), "repository_count": g["repo_id"].nunique()}
        for c in ["pr_total_changed_lines", "pr_changed_files_count", "issue_to_pr_hours", "pr_to_merge_hours"]:
            if c in g.columns:
                row[f"median_{c}"] = pd.to_numeric(g[c], errors="coerce").median()
        for c in ["same_issue_pr_author", "review_activity_present"] + [f"touches_{s}" for s in SURFACES] + [f"has_{t}_marker" for t in AGENT_TOOLS]:
            if c in g.columns:
                row[f"rate_{c}"] = pd.to_numeric(g[c], errors="coerce").mean()
        rows.append(row)
    return pd.DataFrame(rows).sort_values("period")


def stage_temporal(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "09_temporal"
    out.mkdir(parents=True, exist_ok=True)
    if "issue_created_dt" not in df.columns:
        write_json(out / "STATUS.json", {"status":"SKIPPED", "reason":"issue_created_dt missing"})
        return
    monthly = aggregate_period(df, "M")
    quarterly = aggregate_period(df, "Q")
    write_csv(monthly, out / "monthly.csv")
    write_csv(quarterly, out / "quarterly.csv")

    # Simple robust trend: Spearman against time index for series with >=6 populated periods.
    trends = []
    for frame_name, frame in [("monthly", monthly), ("quarterly", quarterly)]:
        if len(frame) < 6:
            continue
        t = np.arange(len(frame))
        for c in frame.select_dtypes(include=[np.number]).columns:
            if c in {"case_count", "repository_count"} or frame[c].notna().sum() < 6:
                continue
            m = frame[c].notna().to_numpy()
            rho, p = stats.spearmanr(t[m], frame.loc[m, c])
            trends.append({"granularity": frame_name, "metric": c, "spearman_time": rho, "p_value": p})
    write_csv(pd.DataFrame(trends), out / "trends.csv")

    # PELT if ruptures is installed.
    cps = []
    try:
        import ruptures as rpt
        for c in [x for x in monthly.select_dtypes(include=[np.number]).columns if x.startswith("median_") or x.startswith("rate_")]:
            s = monthly[c].astype(float).interpolate(limit_direction="both")
            if len(s) < 12 or s.nunique() < 4:
                continue
            arr = s.to_numpy().reshape(-1,1)
            algo = rpt.Pelt(model="rbf", min_size=3).fit(arr)
            bkps = algo.predict(pen=3 * math.log(len(arr)))
            for b in bkps[:-1]:
                pre = float(np.median(arr[max(0,b-3):b]))
                post = float(np.median(arr[b:min(len(arr),b+3)]))
                cps.append({"metric": c, "index": b, "period": monthly.iloc[b]["period"] if b < len(monthly) else "", "pre_value": pre, "post_value": post, "absolute_change": post-pre})
        write_json(out / "PELT_STATUS.json", {"status":"OK", "change_points":len(cps)})
    except Exception as exc:
        write_json(out / "PELT_STATUS.json", {"status":"SKIPPED", "reason":str(exc)})
    write_csv(pd.DataFrame(cps), out / "change_points.csv")


def anomaly_features(df: pd.DataFrame) -> list[str]:
    preferred = [
        "signed_log1p_issue_to_pr_hours", "signed_log1p_pr_to_merge_hours",
        "log1p_pr_total_changed_lines", "log1p_pr_changed_files_count", "log1p_pr_commits_count",
        "num_distinct_change_surfaces", "extension_entropy",
    ]
    return [c for c in preferred if c in df.columns]


def stage_anomalies(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "10_anomalies"
    out.mkdir(parents=True, exist_ok=True)
    feats = anomaly_features(df)
    if len(feats) < 2:
        raise RuntimeError(f"INSUFFICIENT_ANOMALY_FEATURES={feats}")
    X = df[feats].apply(pd.to_numeric, errors="coerce")
    Ximp = X.fillna(X.median())
    Xs = RobustScaler().fit_transform(Ximp)

    mad_rows = []
    mad_scores = np.zeros(len(df))
    for c in feats:
        s = Ximp[c].to_numpy(float)
        med = np.median(s); mad = np.median(np.abs(s-med))
        z = np.abs(s-med) / (1.4826*mad) if mad > 0 else np.zeros_like(s)
        mad_scores = np.maximum(mad_scores, z)
    mad_df = pd.DataFrame({"case_id": df["case_id"], "mad_max_score": mad_scores})
    write_csv(mad_df.sort_values("mad_max_score", ascending=False), out / "robust_scores.csv")

    iso = IsolationForest(n_estimators=500, contamination="auto", random_state=SEED, n_jobs=-1)
    iso.fit(Xs)
    iso_score = -iso.score_samples(Xs)
    idf = pd.DataFrame({"case_id":df["case_id"], "isolation_score":iso_score})
    write_csv(idf.sort_values("isolation_score", ascending=False), out / "isolation_forest.csv")

    nn = min(35, max(10, int(math.sqrt(len(df)))))
    lof = LocalOutlierFactor(n_neighbors=nn, contamination="auto")
    lof.fit_predict(Xs)
    lof_score = -lof.negative_outlier_factor_
    ldf = pd.DataFrame({"case_id":df["case_id"], "lof_score":lof_score})
    write_csv(ldf.sort_values("lof_score", ascending=False), out / "lof.csv")

    # Repository-relative max robust z for repos with >=5 cases.
    repo_score = np.full(len(df), np.nan)
    for repo_id, idx in df.groupby("repo_id").groups.items():
        idx = np.array(list(idx))
        if len(idx) < 5:
            continue
        local = Ximp.loc[idx]
        vals = []
        for c in feats:
            s = local[c].to_numpy(float); med=np.median(s); mad=np.median(np.abs(s-med))
            vals.append(np.abs(s-med)/(1.4826*mad) if mad>0 else np.zeros_like(s))
        repo_score[idx] = np.max(np.vstack(vals), axis=0)
    repodf = pd.DataFrame({"case_id":df["case_id"], "repo_relative_mad_score":repo_score})
    write_csv(repodf.sort_values("repo_relative_mad_score", ascending=False), out / "repository_relative.csv")

    cons = pd.DataFrame({
        "case_id": df["case_id"],
        "mad_max_score": mad_scores,
        "isolation_score": iso_score,
        "lof_score": lof_score,
        "repo_relative_mad_score": repo_score,
    })
    for c in ["mad_max_score","isolation_score","lof_score","repo_relative_mad_score"]:
        cons[f"{c}_pct"] = cons[c].rank(pct=True)
    pct_cols = [c for c in cons.columns if c.endswith("_pct")]
    cons["detector_top1pct_count"] = (cons[pct_cols] >= 0.99).sum(axis=1)
    cons["average_anomaly_percentile"] = cons[pct_cols].mean(axis=1)
    write_csv(cons.sort_values(["detector_top1pct_count","average_anomaly_percentile"], ascending=False), out / "consensus_anomalies.csv")


def clustering_feature_matrix(df: pd.DataFrame):
    numeric_candidates = [
        "signed_log1p_issue_to_pr_hours", "signed_log1p_pr_to_merge_hours",
        "log1p_pr_total_changed_lines", "log1p_pr_changed_files_count", "log1p_pr_commits_count",
        "log1p_pr_review_comments_count", "num_distinct_change_surfaces", "extension_entropy",
        "issue_body_words_auto", "issue_title_words_auto",
    ]
    binary_candidates = [f"touches_{s}" for s in SURFACES] + ["same_issue_pr_author", "review_activity_present"] + [f"has_{t}_marker" for t in AGENT_TOOLS]
    numeric = [c for c in numeric_candidates if c in df.columns]
    binary = [c for c in binary_candidates if c in df.columns]

    # Correlation redundancy pruning among numeric features.
    kept = []
    pruned = []
    for c in numeric:
        if not kept:
            kept.append(c); continue
        redundant_with = None
        for k in kept:
            x = pd.to_numeric(df[c], errors="coerce"); y = pd.to_numeric(df[k], errors="coerce")
            m = x.notna() & y.notna()
            if m.sum() >= 30:
                rho = stats.spearmanr(x[m], y[m]).statistic
                if abs(rho) >= 0.90:
                    redundant_with = k; break
        if redundant_with:
            pruned.append({"feature":c, "reason":"abs_spearman>=0.90", "representative":redundant_with})
        else:
            kept.append(c)
    num = kept
    Xn = df[num].apply(pd.to_numeric, errors="coerce") if num else pd.DataFrame(index=df.index)
    if num:
        Xn = Xn.fillna(Xn.median())
        Xn_scaled = RobustScaler().fit_transform(Xn)
    else:
        Xn_scaled = np.empty((len(df),0))
    Xb = df[binary].fillna(0).astype(float).to_numpy() if binary else np.empty((len(df),0))
    X = np.hstack([Xn_scaled, Xb])
    return X, num + binary, pd.DataFrame(pruned), num, binary


def hdbscan_labels(X):
    # Prefer sklearn HDBSCAN when available, then external package.
    try:
        from sklearn.cluster import HDBSCAN
        model = HDBSCAN(min_cluster_size=max(20, int(0.01*len(X))), min_samples=10, cluster_selection_method="eom")
        return model.fit_predict(X), "sklearn.cluster.HDBSCAN"
    except Exception:
        try:
            import hdbscan
            model = hdbscan.HDBSCAN(min_cluster_size=max(20, int(0.01*len(X))), min_samples=10, cluster_selection_method="eom")
            return model.fit_predict(X), "hdbscan.HDBSCAN"
        except Exception as exc:
            return None, f"UNAVAILABLE: {exc}"


def cluster_metrics(X, labels) -> dict:
    labs = np.asarray(labels)
    non_noise = labs >= 0
    unique = sorted(set(labs[non_noise]))
    out = {"clusters": len(unique), "noise_fraction": float(np.mean(labs < 0))}
    if len(unique) >= 2 and non_noise.sum() > len(unique):
        try: out["silhouette"] = float(silhouette_score(X[non_noise], labs[non_noise]))
        except Exception: out["silhouette"] = np.nan
        try: out["calinski_harabasz"] = float(calinski_harabasz_score(X[non_noise], labs[non_noise]))
        except Exception: out["calinski_harabasz"] = np.nan
        try: out["davies_bouldin"] = float(davies_bouldin_score(X[non_noise], labs[non_noise]))
        except Exception: out["davies_bouldin"] = np.nan
    return out


def gower_like_matrix(df: pd.DataFrame, num: list[str], binary: list[str]) -> np.ndarray:
    parts = []
    if num:
        N = df[num].apply(pd.to_numeric, errors="coerce")
        N = N.fillna(N.median())
        arr = N.to_numpy(float)
        mins = np.nanmin(arr, axis=0); maxs=np.nanmax(arr, axis=0)
        rng = maxs-mins; rng[rng==0]=1
        parts.append((arr-mins)/rng)
    if binary:
        parts.append(df[binary].fillna(0).astype(float).to_numpy())
    X01 = np.hstack(parts) if parts else np.empty((len(df),0))
    if X01.shape[1] == 0:
        raise RuntimeError("No features for Gower-like distance")
    return pdist(X01, metric="cityblock") / X01.shape[1]


def stage_archetypes(runroot: Path) -> None:
    df = load_frame(runroot / "01_data" / "workflow_features")
    out = runroot / "11_archetypes"
    out.mkdir(parents=True, exist_ok=True)
    X, features, pruned, num, binary = clustering_feature_matrix(df)
    write_csv(pd.DataFrame({"feature":features}), out / "clustering_features.csv")
    write_csv(pruned, out / "clustering_feature_pruning.csv")

    model_rows = []
    assignments = pd.DataFrame({"case_id":df["case_id"]})

    # KMeans baseline.
    best_km = None
    for k in range(2, min(15, len(df)-1)+1):
        lab = KMeans(n_clusters=k, n_init=50, random_state=SEED).fit_predict(X)
        met = cluster_metrics(X, lab); met.update({"method":"kmeans", "param":f"k={k}"})
        model_rows.append(met)
        score = met.get("silhouette", np.nan)
        if np.isfinite(score) and (best_km is None or score > best_km[0]):
            best_km = (score, k, lab)
    if best_km:
        assignments["kmeans_best"] = best_km[2]

    # HDBSCAN.
    hlabels, himpl = hdbscan_labels(X)
    if hlabels is not None:
        met = cluster_metrics(X, hlabels); met.update({"method":"hdbscan", "param":himpl})
        model_rows.append(met)
        assignments["hdbscan"] = hlabels
    else:
        write_json(out / "HDBSCAN_STATUS.json", {"status":"SKIPPED", "reason":himpl})

    # Gower-like mixed distance + hierarchical; choose k by silhouette on precomputed distance.
    gd = gower_like_matrix(df, num, binary)
    Z = linkage(gd, method="average")
    Gsquare = squareform(gd)
    best_g = None
    for k in range(2, min(15, len(df)-1)+1):
        lab = fcluster(Z, k, criterion="maxclust") - 1
        try: sil = silhouette_score(Gsquare, lab, metric="precomputed")
        except Exception: sil = np.nan
        met = {"method":"gower_hierarchical", "param":f"k={k}", "clusters":len(set(lab)), "noise_fraction":0.0, "silhouette":sil}
        model_rows.append(met)
        if np.isfinite(sil) and (best_g is None or sil > best_g[0]):
            best_g = (sil,k,lab)
    if best_g:
        assignments["gower_hierarchical_best"] = best_g[2]

    write_csv(pd.DataFrame(model_rows), out / "model_selection.csv")
    write_csv(assignments, out / "assignments_by_method.csv")

    # Repository-blocked stability for chosen methods.
    repos = np.array(sorted(df["repo_id"].dropna().unique()))
    rng = np.random.default_rng(SEED + 33)
    repo_samples = [set(rng.choice(repos, size=max(1,int(len(repos)*REPO_SAMPLE_FRAC)), replace=False).tolist()) for _ in range(RESAMPLES)]
    base_map = {"kmeans": assignments.get("kmeans_best"), "hdbscan": assignments.get("hdbscan"), "gower": assignments.get("gower_hierarchical_best")}

    def one_resample(sample_i, chosen):
        idx = np.flatnonzero(df["repo_id"].isin(chosen).to_numpy())
        sub = df.iloc[idx]
        Xs, _, _, nsub, bsub = clustering_feature_matrix(sub)
        rec = {"n":len(idx)}
        if best_km:
            lab = KMeans(n_clusters=best_km[1], n_init=20, random_state=SEED).fit_predict(Xs)
            full = np.asarray(assignments["kmeans_best"])[idx]
            rec["kmeans_ari"] = adjusted_rand_score(full, lab)
            rec["kmeans_nmi"] = normalized_mutual_info_score(full, lab)
        if hlabels is not None:
            lab, _ = hdbscan_labels(Xs)
            if lab is not None:
                full = np.asarray(assignments["hdbscan"])[idx]
                rec["hdbscan_ari"] = adjusted_rand_score(full, lab)
                rec["hdbscan_nmi"] = normalized_mutual_info_score(full, lab)
        if best_g and sample_i < GOWER_RESAMPLES:
            gd_s = gower_like_matrix(sub, nsub, bsub)
            Zs = linkage(gd_s, method="average")
            lab = fcluster(Zs, best_g[1], criterion="maxclust") - 1
            full = np.asarray(assignments["gower_hierarchical_best"])[idx]
            rec["gower_ari"] = adjusted_rand_score(full, lab)
            rec["gower_nmi"] = normalized_mutual_info_score(full, lab)
        return rec

    n_jobs = max(1, min(int(os.environ.get("SLURM_CPUS_PER_TASK", "8")), 24))
    if Parallel is not None:
        stab = Parallel(n_jobs=n_jobs, backend="loky")(delayed(one_resample)(i, s) for i, s in enumerate(repo_samples))
    else:
        stab = [one_resample(i, s) for i, s in enumerate(repo_samples)]
    sdf = pd.DataFrame(stab)
    write_csv(sdf, out / "cluster_stability_iterations.csv")
    summary = []
    for c in sdf.columns:
        if c == "n": continue
        x = sdf[c].dropna()
        if len(x):
            summary.append({"metric":c, "median":x.median(), "p025":x.quantile(0.025), "p975":x.quantile(0.975)})
    write_csv(pd.DataFrame(summary), out / "cluster_stability.csv")

    # Consensus across available full-data solutions only; resampling stability reported separately.
    label_cols = [c for c in ["kmeans_best","hdbscan","gower_hierarchical_best"] if c in assignments.columns]
    if len(label_cols) >= 2:
        n = len(df); co = np.zeros((n,n), dtype=np.float32); denom=np.zeros((n,n), dtype=np.float32)
        for c in label_cols:
            labs = assignments[c].to_numpy()
            valid = labs >= 0
            ids = np.flatnonzero(valid)
            denom[np.ix_(ids,ids)] += 1.0
            for lab in sorted(set(labs[valid])):
                members = np.flatnonzero(labs == lab)
                co[np.ix_(members,members)] += 1.0
        sim = np.divide(co, denom, out=np.zeros_like(co), where=denom>0)
        dist = 1.0 - sim
        np.fill_diagonal(dist, 0.0)
        best_cons = None
        for k in range(2, 11):
            try:
                model = AgglomerativeClustering(n_clusters=k, metric="precomputed", linkage="average")
            except TypeError:
                model = AgglomerativeClustering(n_clusters=k, affinity="precomputed", linkage="average")
            lab = model.fit_predict(dist)
            sil = silhouette_score(dist, lab, metric="precomputed")
            if best_cons is None or sil > best_cons[0]: best_cons=(sil,k,lab)
        if best_cons:
            cdf = pd.DataFrame({"case_id":df["case_id"], "consensus_archetype":best_cons[2]})
            write_csv(cdf, out / "consensus_archetypes.csv")
            write_json(out / "CONSENSUS_STATUS.json", {"methods":label_cols, "k":best_cons[1], "silhouette":best_cons[0]})


def stage_text(runroot: Path) -> None:
    out = runroot / "12_text_optional"
    out.mkdir(parents=True, exist_ok=True)
    text = load_frame(runroot / "01_data" / "issue_pr_text")
    if "issue_title" not in text.columns or "issue_body" not in text.columns:
        write_json(out / "STATUS.json", {"status":"SKIPPED", "reason":"issue title/body unavailable"})
        return
    docs = (text["issue_title"].fillna("").astype(str) + "\n" + text["issue_body"].fillna("").astype(str))
    docs = docs.str.replace(r"https?://\S+", " URL ", regex=True)
    docs = docs.str.replace(r"\b[a-f0-9]{12,64}\b", " HASH ", regex=True)
    docs = docs.str.replace(r"#\d+\b", " ISSUE_NUM ", regex=True)
    vec = TfidfVectorizer(lowercase=True, ngram_range=(1,2), min_df=10, max_df=0.80, max_features=20000, strip_accents="unicode")
    X = vec.fit_transform(docs)
    vocab = pd.DataFrame({"term":vec.get_feature_names_out()})
    write_csv(vocab, out / "vocabulary.csv")

    rows=[]; best=None
    for k in TEXT_TOPIC_KS:
        if k >= X.shape[0] or k >= X.shape[1]: continue
        for seed in [SEED, SEED+1, SEED+2, SEED+3, SEED+4]:
            model=NMF(n_components=k, init="nndsvda", random_state=seed, max_iter=500)
            W=model.fit_transform(X)
            err=float(model.reconstruction_err_)
            terms=vec.get_feature_names_out()
            top=[tuple(terms[np.argsort(comp)[-10:][::-1]]) for comp in model.components_]
            diversity=len(set(itertools.chain.from_iterable(top)))/(k*10)
            rows.append({"k":k,"seed":seed,"reconstruction_error":err,"top_term_diversity":diversity})
        krows=[r for r in rows if r["k"]==k]
        mederr=statistics.median(r["reconstruction_error"] for r in krows)
        meddiv=statistics.median(r["top_term_diversity"] for r in krows)
        score=meddiv/(1+mederr/max(1,X.shape[0]))
        if best is None or score>best[0]: best=(score,k)
    write_csv(pd.DataFrame(rows), out / "nmf_model_selection.csv")
    if not best:
        write_json(out / "STATUS.json", {"status":"SKIPPED", "reason":"no feasible topic count"}); return
    k=best[1]
    model=NMF(n_components=k, init="nndsvda", random_state=SEED, max_iter=800)
    W=model.fit_transform(X); terms=vec.get_feature_names_out()
    topic_rows=[]
    for j, comp in enumerate(model.components_):
        top=terms[np.argsort(comp)[-20:][::-1]]
        topic_rows.append({"topic_id":f"T{j+1:02d}","top_terms":" | ".join(top)})
    write_csv(pd.DataFrame(topic_rows), out / "topics.csv")
    assign=np.argmax(W, axis=1)
    adf=pd.DataFrame({"case_id":text["case_id"],"topic_id":[f"T{x+1:02d}" for x in assign],"topic_weight":W.max(axis=1)})
    write_csv(adf, out / "topic_assignments.csv")


def stage_report(runroot: Path) -> None:
    out = runroot
    idx_rows=[]
    def add_from(path, typ, desc_cols, score_cols, limit=50):
        if not path.exists(): return
        try: df=pd.read_csv(path)
        except Exception: return
        for n, r in df.head(limit).iterrows():
            desc="; ".join(f"{c}={r.get(c)}" for c in desc_cols if c in df.columns)
            score="; ".join(f"{c}={r.get(c)}" for c in score_cols if c in df.columns)
            idx_rows.append({"discovery_id":f"{typ}-{len(idx_rows)+1:04d}","type":typ,"description":desc,"score_summary":score,"artifact_path":str(path.relative_to(runroot))})
    add_from(runroot/"04_signatures"/"ranked_signatures.csv","SIG",["signature_type","signature"],["case_count","repository_count","support"])
    add_from(runroot/"05_patterns"/"association_rules.csv","PAT",["antecedent","consequent"],["support","confidence","lift"])
    add_from(runroot/"07_relationships"/"spearman.csv","REL",["a","b"],["spearman_rho","n"])
    add_from(runroot/"10_anomalies"/"consensus_anomalies.csv","ANO",["case_id"],["detector_top1pct_count","average_anomaly_percentile"])
    add_from(runroot/"09_temporal"/"trends.csv","TMP",["granularity","metric"],["spearman_time"])
    add_from(runroot/"06_topology"/"topology_frequency.csv","TOP",["topology"],["components","nodes"])
    write_csv(pd.DataFrame(idx_rows), runroot/"14_discovery_index"/"DISCOVERY_INDEX.csv")

    lines=[]
    lines.append("# Full-Corpus Outcome-Blind Workflow Discovery v1.1")
    lines.append("")
    lines.append("## Scope")
    lines.append("This report is descriptive and outcome-blind. Scanner/security outcomes and manual security annotations were excluded from the discovery pipeline.")
    lines.append("")
    try:
        inv=json.loads((runroot/"02_quality"/"invariants.json").read_text())
        lines.append("## Corpus")
        lines.append(f"- Workflows: {inv.get('rows')}")
        lines.append(f"- Unique cases: {inv.get('unique_case_ids')}")
        lines.append(f"- Repositories: {inv.get('repositories')}")
        lines.append("")
    except Exception: pass

    sections=[
        ("Most common workflow signatures", runroot/"04_signatures"/"ranked_signatures.csv", ["signature_type","signature","case_count","repository_count","support"]),
        ("Strong recurring association rules", runroot/"05_patterns"/"association_rules.csv", ["antecedent","consequent","support","confidence","lift"]),
        ("Strong numeric relationships", runroot/"07_relationships"/"spearman.csv", ["a","b","spearman_rho","n"]),
        ("Issue/PR topology frequencies", runroot/"06_topology"/"topology_frequency.csv", ["topology","components","nodes"]),
        ("Temporal trends", runroot/"09_temporal"/"trends.csv", ["granularity","metric","spearman_time"]),
        ("Top consensus anomalies", runroot/"10_anomalies"/"consensus_anomalies.csv", ["case_id","detector_top1pct_count","average_anomaly_percentile","repo_relative_mad_score"]),
        ("Clustering stability", runroot/"11_archetypes"/"cluster_stability.csv", ["metric","median","p025","p975"]),
    ]
    for title,path,cols in sections:
        lines.append(f"## {title}")
        if not path.exists():
            lines.append("Module output unavailable."); lines.append(""); continue
        try: d=pd.read_csv(path).head(20)
        except Exception as exc:
            lines.append(f"Could not read output: {exc}"); lines.append(""); continue
        keep=[c for c in cols if c in d.columns]
        if not keep or d.empty:
            lines.append("No qualifying results."); lines.append(""); continue
        view = d[keep].copy()
        headers = [str(c) for c in keep]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        for _, rr in view.iterrows():
            vals = []
            for c in keep:
                v = rr[c]
                if pd.isna(v):
                    txt = ""
                else:
                    txt = str(v).replace("|", "\\|").replace("\n", " ")
                vals.append(txt)
            lines.append("| " + " | ".join(vals) + " |")
        lines.append("")
    lines.append("## Interpretation boundary")
    lines.append("No pattern in this report is labeled high-risk, low-risk, malicious, benign, vulnerable, secure, attack-like, or predictive. Those questions require a separate later study.")
    lines.append("")
    lines.append("**DISCOVERY_COMPLETE — OUTCOME_OVERLAY_NOT_PERFORMED**")
    (runroot/"DISCOVERY_REPORT.md").write_text("\n".join(lines), encoding="utf-8")

    # Checksums over files except checksums file itself.
    rows=[]
    for p in sorted(runroot.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS.tsv":
            try: rows.append({"sha256":sha256_file(p),"path":str(p.relative_to(runroot))})
            except Exception: pass
    write_csv(pd.DataFrame(rows), runroot/"00_manifest"/"SHA256SUMS.tsv")
    write_json(runroot/"00_manifest"/"FINAL_STATUS.json", {
        "status":"PASS",
        "completed_at":now_iso(),
        "discovery_complete":True,
        "outcome_overlay_performed":False,
    })


def write_checkpoint(runroot: Path, stage: str, status: str, detail: str = ""):
    d=runroot/"checkpoints"; d.mkdir(parents=True, exist_ok=True)
    write_json(d/f"{stage}.json", {"stage":stage,"status":status,"detail":detail,"timestamp":now_iso()})


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--stage", required=True, choices=["extract","quality","landscape","signatures","patterns","topology","relationships","repository","temporal","anomalies","archetypes","text","report"])
    ap.add_argument("--runroot", required=True)
    ap.add_argument("--db")
    ap.add_argument("--repo")
    args=ap.parse_args()
    runroot=Path(args.runroot).resolve(); runroot.mkdir(parents=True, exist_ok=True)
    stage=args.stage
    try:
        write_checkpoint(runroot, stage, "RUNNING")
        if stage=="extract":
            if not args.db or not args.repo: raise RuntimeError("extract requires --db and --repo")
            stage_extract(runroot, Path(args.db), Path(args.repo))
        elif stage=="quality": stage_quality(runroot)
        elif stage=="landscape": stage_landscape(runroot)
        elif stage=="signatures": stage_signatures(runroot)
        elif stage=="patterns": stage_patterns(runroot)
        elif stage=="topology": stage_topology(runroot)
        elif stage=="relationships": stage_relationships(runroot)
        elif stage=="repository": stage_repository(runroot)
        elif stage=="temporal": stage_temporal(runroot)
        elif stage=="anomalies": stage_anomalies(runroot)
        elif stage=="archetypes": stage_archetypes(runroot)
        elif stage=="text": stage_text(runroot)
        elif stage=="report": stage_report(runroot)
        write_checkpoint(runroot, stage, "PASS")
        print(f"STAGE_STATUS={stage}=PASS", flush=True)
    except Exception as exc:
        err=runroot/"logs"/f"{stage}.exception.txt"; err.parent.mkdir(parents=True, exist_ok=True)
        err.write_text(traceback.format_exc(), encoding="utf-8")
        if stage == "text":
            write_checkpoint(runroot, stage, "OPTIONAL_FAILED", f"{type(exc).__name__}: {exc}")
            write_json(runroot/"12_text_optional"/"STATUS.json", {"status":"OPTIONAL_FAILED", "reason":f"{type(exc).__name__}: {exc}"})
            print(f"STAGE_STATUS={stage}=OPTIONAL_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return
        write_checkpoint(runroot, stage, "FAIL", f"{type(exc).__name__}: {exc}")
        print(f"STAGE_STATUS={stage}=FAIL: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise

if __name__=="__main__":
    main()
