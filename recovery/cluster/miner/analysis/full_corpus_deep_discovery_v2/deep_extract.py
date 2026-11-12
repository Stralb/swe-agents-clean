from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from deep_common import (
    EXPECTED_CASES, EXPECTED_DB_SHA256, FORBIDDEN_COLUMN_PATTERNS,
    FORBIDDEN_TABLE_PATTERNS, SUBJECTIVE_COLUMN_PATTERNS,
    column_forbidden, column_subjective, is_text_name, is_time_name,
    list_tables, load_frame, now_iso, open_ro, quote_ident, safe_columns_for_table,
    safe_read_sql, save_frame, sha256_file, table_columns, table_forbidden,
    write_csv, write_json,
)

CORE_TABLES = ["cases", "repos", "issues", "pull_requests", "pr_files"]
RAW_TEXT_FIELDS = {
    "issues": ["title", "body"],
    "pull_requests": ["title", "body"],
}


def _case_map(cases: pd.DataFrame, key: str) -> pd.DataFrame:
    return cases[["case_id", key]].dropna().drop_duplicates()


def _safe_select(con, table: str, log: Path, extra_subjective_exclusion: bool = True) -> pd.DataFrame:
    cols = safe_columns_for_table(con, table, exclude_subjective=extra_subjective_exclusion)
    if not cols:
        return pd.DataFrame()
    sql = "SELECT " + ", ".join(quote_ident(c) for c in cols) + f" FROM {quote_ident(table)}"
    return safe_read_sql(con, sql, log, table=table)


def _prefix_frame(df: pd.DataFrame, prefix: str, keep: set[str]) -> pd.DataFrame:
    ren = {c: c if c in keep else f"{prefix}__{c}" for c in df.columns}
    return df.rename(columns=ren)


def _coerce_time_series(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=True)


def _generic_case_aggregate(table: str, df: pd.DataFrame, cases: pd.DataFrame) -> tuple[pd.DataFrame | None, dict]:
    """Aggregate any safe relational table to case-level without assuming domain semantics."""
    info = {"table": table, "rows": int(len(df)), "status": ""}
    if df.empty:
        info["status"] = "EMPTY"
        return None, info

    join_key = None
    for k in ["case_id", "pr_id", "issue_id", "repo_id"]:
        if k in df.columns:
            join_key = k
            break
    if not join_key:
        info["status"] = "NO_CASE_LINK_KEY"
        return None, info

    if join_key == "case_id":
        x = df.copy()
    else:
        cmap = _case_map(cases, join_key)
        x = cmap.merge(df, on=join_key, how="left")

    if "case_id" not in x.columns:
        info["status"] = "CASE_JOIN_FAILED"
        return None, info

    # Exclude linkage columns from generic value summaries.
    skip = {"case_id", "repo_id", "issue_id", "pr_id", "id"}
    value_cols = [c for c in x.columns if c not in skip]

    rows = []
    for case_id, g in x.groupby("case_id", sort=False, dropna=False):
        row = {"case_id": case_id, f"rel__{table}__row_count": int(len(g))}
        for c in value_cols:
            s = g[c]
            base = f"rel__{table}__{c}"

            # Time-like fields get generic temporal summaries.
            if is_time_name(c):
                t = _coerce_time_series(s)
                valid = t.dropna()
                row[base + "__nonmissing"] = int(valid.size)
                if valid.size:
                    row[base + "__span_hours"] = float((valid.max() - valid.min()).total_seconds() / 3600.0)
                    row[base + "__age_order_nunique"] = int(valid.nunique())
                continue

            num = pd.to_numeric(s, errors="coerce")
            numeric_fraction = float(num.notna().mean()) if len(s) else 0.0
            # Numeric if source dtype is numeric OR almost all non-null values parse numerically.
            if pd.api.types.is_numeric_dtype(s) or numeric_fraction >= 0.95:
                v = num.dropna()
                row[base + "__nonmissing"] = int(v.size)
                if v.size:
                    row[base + "__mean"] = float(v.mean())
                    row[base + "__std"] = float(v.std(ddof=1)) if v.size > 1 else 0.0
                    row[base + "__min"] = float(v.min())
                    row[base + "__max"] = float(v.max())
                    row[base + "__sum"] = float(v.sum())
                    row[base + "__nunique"] = int(v.nunique())
                continue

            # Generic strings: only structural properties, not semantics.
            txt = s.dropna().astype(str)
            row[base + "__nonmissing"] = int(len(txt))
            if len(txt):
                lens = txt.str.len()
                vc = txt.value_counts(dropna=False)
                row[base + "__strlen_mean"] = float(lens.mean())
                row[base + "__strlen_max"] = float(lens.max())
                row[base + "__nunique"] = int(txt.nunique())
                row[base + "__top_share"] = float(vc.iloc[0] / len(txt)) if len(vc) else np.nan
        rows.append(row)

    info["status"] = "AGGREGATED"
    info["case_rows"] = int(len(rows))
    return pd.DataFrame(rows), info


def stage_extract(runroot: Path, db: Path, repo: Path) -> None:
    runroot.mkdir(parents=True, exist_ok=True)
    (runroot / "00_manifest").mkdir(parents=True, exist_ok=True)
    (runroot / "01_raw").mkdir(parents=True, exist_ok=True)
    log = runroot / "logs" / "sql_access_v2.log"

    test_mode = os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1"
    actual_sha = sha256_file(db)
    if not test_mode and actual_sha != EXPECTED_DB_SHA256:
        raise RuntimeError(f"DB_SHA256_MISMATCH expected={EXPECTED_DB_SHA256} actual={actual_sha}")

    con = open_ro(db)
    tables = list_tables(con)
    inventory = []
    schemas = {}
    for t in tables:
        cols = table_columns(con, t)
        schemas[t] = cols
        inventory.append({
            "table": t,
            "forbidden_by_name": bool(table_forbidden(t)),
            "column_count": len(cols),
            "columns": " | ".join(x["name"] for x in cols),
        })
    write_csv(pd.DataFrame(inventory), runroot / "00_manifest" / "TABLE_INVENTORY.csv")
    write_json(runroot / "00_manifest" / "SCHEMA_SNAPSHOT.json", schemas)
    write_json(runroot / "00_manifest" / "OUTCOME_BLINDING_POLICY.json", {
        "forbidden_table_patterns": FORBIDDEN_TABLE_PATTERNS,
        "forbidden_column_patterns": FORBIDDEN_COLUMN_PATTERNS,
        "subjective_column_patterns": SUBJECTIVE_COLUMN_PATTERNS,
        "principle": "Schema inventory is allowed. Contents of forbidden tables and forbidden/manual/security columns are never read.",
    })

    missing = [t for t in CORE_TABLES if t not in tables]
    if missing:
        raise RuntimeError(f"MISSING_CORE_TABLES={missing}")

    # Linkage only from cases.
    ccols = [x["name"] for x in schemas["cases"]]
    needed = ["id", "repo_id", "issue_id", "pr_id"]
    if not all(c in ccols for c in needed):
        raise RuntimeError(f"CASES_LINKAGE_MISSING={needed}")
    cases = safe_read_sql(
        con,
        "SELECT id AS case_id, repo_id, issue_id, pr_id FROM cases ORDER BY id",
        log,
        table="cases",
    )
    expected = EXPECTED_CASES if not test_mode else len(cases)
    if len(cases) != expected or cases["case_id"].nunique() != expected:
        raise RuntimeError(f"CASE_INVARIANT_FAIL rows={len(cases)} unique={cases['case_id'].nunique()} expected={expected}")
    save_frame(cases, runroot / "01_raw" / "cases_linkage")

    # Core entity tables: explicit safe columns, preserving raw objective fields.
    entity_specs = [
        ("repos", "repo_id", "id", "repo"),
        ("issues", "issue_id", "id", "issue"),
        ("pull_requests", "pr_id", "id", "pr"),
    ]
    case_features = cases.copy()
    raw_text = cases.copy()
    access_rows = []

    for table, case_fk, table_pk, prefix in entity_specs:
        cols = safe_columns_for_table(con, table, exclude_subjective=True)
        if table_pk not in cols:
            raise RuntimeError(f"{table} missing primary linkage {table_pk}")
        sql = "SELECT " + ", ".join(quote_ident(c) for c in cols) + f" FROM {quote_ident(table)}"
        edf = safe_read_sql(con, sql, log, table=table)
        edf = edf.rename(columns={table_pk: case_fk})
        edf = _prefix_frame(edf, prefix, {case_fk})

        # Save raw safe entity table.
        save_frame(edf, runroot / "01_raw" / f"{table}_safe")

        # Separate text into raw text store; case_features receives only generic text lengths.
        text_cols = [c for c in edf.columns if c != case_fk and is_text_name(c)]
        if text_cols:
            tdf = cases[["case_id", case_fk]].merge(edf[[case_fk] + text_cols], on=case_fk, how="left")
            for c in text_cols:
                raw_text[c] = tdf.set_index("case_id")[c].reindex(raw_text["case_id"]).to_numpy()

        scalar = edf.copy()
        for c in text_cols:
            scalar[c + "__chars"] = scalar[c].fillna("").astype(str).str.len()
            scalar[c + "__words"] = scalar[c].fillna("").astype(str).str.findall(r"\b\w+\b").str.len()
            scalar[c + "__lines"] = scalar[c].fillna("").astype(str).str.count("\n") + 1
        scalar = scalar.drop(columns=text_cols, errors="ignore")
        case_features = case_features.merge(scalar, on=case_fk, how="left")
        access_rows.append({"table": table, "status": "CORE_SAFE_READ", "columns_read": len(cols)})

    # PR files are first-class raw material, including patch if objectively stored.
    pf_cols = safe_columns_for_table(con, "pr_files", exclude_subjective=True)
    pf_sql = "SELECT " + ", ".join(quote_ident(c) for c in pf_cols) + " FROM pr_files"
    pr_files = safe_read_sql(con, pf_sql, log, table="pr_files")
    pr_files = cases[["case_id", "pr_id", "repo_id"]].merge(pr_files, on="pr_id", how="left")
    save_frame(pr_files, runroot / "01_raw" / "pr_files_with_patch")
    access_rows.append({"table": "pr_files", "status": "CORE_SAFE_READ_WITH_PATCH", "columns_read": len(pf_cols)})

    # Generic case-level PR-file scalar aggregation; patch content itself is excluded from scalar values.
    pf_for_agg = pr_files.drop(columns=[c for c in pr_files.columns if is_text_name(c)], errors="ignore")
    pf_agg, pf_info = _generic_case_aggregate("pr_files", pf_for_agg, cases)
    if pf_agg is not None:
        case_features = case_features.merge(pf_agg, on="case_id", how="left")
    access_rows.append(pf_info)

    # Generic relational discovery: use every other non-forbidden table that can be linked to a case.
    # Unknown text is summarized structurally (length/cardinality), not semantically embedded.
    generic_aggs = []
    for table in tables:
        if table in CORE_TABLES:
            continue
        if table_forbidden(table):
            access_rows.append({"table": table, "status": "BLOCKED_FORBIDDEN_TABLE"})
            continue
        safe_cols = safe_columns_for_table(con, table, exclude_subjective=True)
        join_candidates = [k for k in ["case_id", "pr_id", "issue_id", "repo_id"] if k in safe_cols]
        if not join_candidates:
            access_rows.append({"table": table, "status": "SAFE_BUT_NOT_CASE_LINKABLE", "columns_read": 0})
            continue
        if not safe_cols:
            access_rows.append({"table": table, "status": "NO_SAFE_COLUMNS", "columns_read": 0})
            continue

        # All selected column names are explicit; never SELECT *.
        sql = "SELECT " + ", ".join(quote_ident(c) for c in safe_cols) + f" FROM {quote_ident(table)}"
        try:
            df = safe_read_sql(con, sql, log, table=table)
        except Exception as exc:
            access_rows.append({"table": table, "status": "READ_ERROR", "detail": repr(exc)})
            continue
        # Automatically preserve safe relational text as its own case-level text fields.
        join_key = next((k for k in ["case_id","pr_id","issue_id","repo_id"] if k in df.columns), None)
        if join_key:
            if join_key == "case_id":
                tx = df.copy()
            else:
                tx = _case_map(cases, join_key).merge(df, on=join_key, how="left")
            for tc in [c for c in safe_cols if is_text_name(c) and c.lower() != "patch"]:
                if tc not in tx.columns:
                    continue
                joined = tx.groupby("case_id")[tc].apply(
                    lambda z: "\n".join(z.dropna().astype(str).tolist())[:200000]
                )
                if (joined.str.len() > 0).sum() >= 10:
                    col = f"reltext__{table}__{tc}"
                    raw_text[col] = raw_text["case_id"].map(joined).fillna("")

        agg, info = _generic_case_aggregate(table, df, cases)
        info["columns_read"] = len(safe_cols)
        access_rows.append(info)
        if agg is not None:
            generic_aggs.append(agg)
            save_frame(agg, runroot / "01_raw" / f"generic_aggregate__{table}")

    for agg in generic_aggs:
        case_features = case_features.merge(agg, on="case_id", how="left")

    # Derive generic time deltas from all time-like case-level entity columns.
    time_cols = [c for c in case_features.columns if is_time_name(c)]
    for c in time_cols:
        case_features[c + "__parsed"] = pd.to_datetime(case_features[c], errors="coerce", utc=True)
    parsed = [c for c in case_features.columns if c.endswith("__parsed")]
    # Pairwise time deltas are generic and exhaustive, but only among <=20 timestamp fields to avoid pathological schemas.
    parsed = parsed[:20]
    for i, a in enumerate(parsed):
        for b in parsed[i + 1:]:
            aa = case_features[a]
            bb = case_features[b]
            name = f"delta_hours__{a[:-8]}__to__{b[:-8]}"
            case_features[name] = (bb - aa).dt.total_seconds() / 3600.0
    case_features = case_features.drop(columns=parsed, errors="ignore")

    # Preserve text separately. Prefix names make views discoverable rather than predetermined questions.
    raw_text = raw_text.drop(columns=[c for c in ["repo_id", "issue_id", "pr_id"] if c in raw_text.columns])
    save_frame(raw_text, runroot / "01_raw" / "case_text")
    save_frame(case_features, runroot / "01_raw" / "case_scalar_features")

    # Patch coverage audit from metadata vs stored unified-diff lines.
    coverage_rows = []
    patch_col = next((c for c in pr_files.columns if c.lower() == "patch"), None)
    add_col = next((c for c in pr_files.columns if c.lower() == "additions"), None)
    del_col = next((c for c in pr_files.columns if c.lower() == "deletions"), None)
    for cid, g in pr_files.groupby("case_id", sort=False):
        meta_add = float(pd.to_numeric(g[add_col], errors="coerce").fillna(0).sum()) if add_col else np.nan
        meta_del = float(pd.to_numeric(g[del_col], errors="coerce").fillna(0).sum()) if del_col else np.nan
        p_add = p_del = bytes_ = files_with_patch = 0
        if patch_col:
            for p in g[patch_col].dropna().astype(str):
                if not p.strip():
                    continue
                files_with_patch += 1
                bytes_ += len(p.encode("utf-8", errors="replace"))
                for line in p.splitlines():
                    if line.startswith("+++") or line.startswith("---"):
                        continue
                    if line.startswith("+"):
                        p_add += 1
                    elif line.startswith("-"):
                        p_del += 1
        denom = (meta_add + meta_del) if pd.notna(meta_add) and pd.notna(meta_del) else np.nan
        ratio = min(1.0, (p_add + p_del) / denom) if pd.notna(denom) and denom > 0 else (1.0 if p_add + p_del > 0 else np.nan)
        coverage_rows.append({
            "case_id": cid,
            "file_rows": int(len(g)),
            "files_with_patch": int(files_with_patch),
            "metadata_changed_lines": denom,
            "stored_patch_changed_lines": int(p_add + p_del),
            "patch_line_coverage_ratio": ratio,
            "patch_bytes": int(bytes_),
        })
    coverage = pd.DataFrame(coverage_rows)
    write_csv(coverage, runroot / "01_raw" / "patch_coverage.csv")

    write_csv(pd.DataFrame(access_rows), runroot / "00_manifest" / "TABLE_ACCESS_AUDIT.csv")
    con.close()

    write_json(runroot / "00_manifest" / "RUN_MANIFEST.json", {
        "method": "Full-Corpus Schema-Driven Multi-View Discovery v2.0",
        "created_at": now_iso(),
        "source_db": str(db.resolve()),
        "db_sha256": actual_sha,
        "expected_db_sha256": EXPECTED_DB_SHA256,
        "expected_cases": expected,
        "observed_cases": int(len(cases)),
        "repo": str(repo.resolve()),
        "outcome_overlay_performed": False,
        "security_outcomes_read": False,
        "analysis_principle": "Generic discovery operators over every safely accessible objective representation; interpretation follows discovery.",
    })
    write_json(runroot / "00_manifest" / "EXTRACT_SUMMARY.json", {
        "cases": int(len(cases)),
        "repositories": int(cases["repo_id"].nunique()),
        "scalar_features": int(case_features.shape[1]),
        "text_fields": int(raw_text.shape[1] - 1),
        "pr_file_rows": int(len(pr_files)),
        "patch_column_present": bool(patch_col),
        "patch_cases_any_content": int((coverage["files_with_patch"] > 0).sum()),
        "patch_cases_coverage_ge_0_8": int((coverage["patch_line_coverage_ratio"] >= 0.8).sum()),
        "safe_tables_aggregated": int(sum(1 for x in access_rows if x.get("status") == "AGGREGATED")),
    })


def stage_quality(runroot: Path) -> None:
    out = runroot / "02_quality"
    out.mkdir(parents=True, exist_ok=True)
    df = load_frame(runroot / "01_raw" / "case_scalar_features")
    cov = pd.read_csv(runroot / "01_raw" / "patch_coverage.csv")
    test_mode = os.environ.get("DEEP_DISCOVERY_TEST_MODE") == "1"
    expected = len(df) if test_mode else EXPECTED_CASES

    inv = {
        "rows": int(len(df)),
        "unique_case_ids": int(df["case_id"].nunique()),
        "repositories": int(df["repo_id"].nunique()),
        "expected_cases": int(expected),
        "case_invariant_pass": bool(len(df) == expected and df["case_id"].nunique() == expected),
        "duplicate_case_ids": int(df.duplicated("case_id").sum()),
    }
    write_json(out / "invariants.json", inv)
    if not inv["case_invariant_pass"]:
        raise RuntimeError(f"QUALITY_CASE_INVARIANT_FAIL={inv}")

    miss = []
    for c in df.columns:
        miss.append({
            "feature": c,
            "dtype": str(df[c].dtype),
            "missing_count": int(df[c].isna().sum()),
            "missing_fraction": float(df[c].isna().mean()),
            "nunique": int(df[c].nunique(dropna=True)),
        })
    write_csv(pd.DataFrame(miss).sort_values(["missing_fraction", "feature"], ascending=[False, True]), out / "missingness.csv")

    # Numeric extremes via robust z, no deletion/winsorization.
    ex = []
    numeric = [c for c in df.select_dtypes(include=[np.number]).columns if c != "case_id"]
    for c in numeric:
        s = pd.to_numeric(df[c], errors="coerce")
        med = s.median(); mad = (s-med).abs().median()
        if pd.isna(mad) or mad <= 0:
            continue
        z = 0.6744897501960817 * (s-med)/mad
        idx = z.abs().nlargest(min(20, z.notna().sum())).index
        for i in idx:
            ex.append({"case_id": df.at[i, "case_id"], "feature": c, "value": s.at[i], "robust_z": z.at[i]})
    write_csv(pd.DataFrame(ex), out / "numeric_extremes.csv")

    write_json(out / "patch_coverage_summary.json", {
        "cases": int(len(cov)),
        "any_patch": int((cov["files_with_patch"] > 0).sum()),
        "coverage_ge_0_95": int((cov["patch_line_coverage_ratio"] >= 0.95).sum()),
        "coverage_ge_0_80": int((cov["patch_line_coverage_ratio"] >= 0.80).sum()),
        "coverage_lt_0_50": int((cov["patch_line_coverage_ratio"] < 0.50).sum()),
        "no_patch": int((cov["files_with_patch"] == 0).sum()),
        "total_patch_mb": float(cov["patch_bytes"].sum() / 1024 / 1024),
    })
