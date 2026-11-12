from __future__ import annotations

import itertools
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.compose import ColumnTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

from deep_common import (
    SEED, codeish_tokenize, is_identifier_name, is_text_name, is_time_name,
    load_frame, normalize_text_for_similarity, path_tokens, save_embedding,
    save_frame, save_sparse, write_csv, write_json,
)


def _svd_embedding(X, case_ids, outbase: Path, n_components: int = 128, feature_names=None, random_state: int = SEED):
    max_comp = min(n_components, max(1, X.shape[0] - 1), max(1, X.shape[1] - 1))
    if X.shape[1] < 2 or X.shape[0] < 3:
        E = X.toarray() if sparse.issparse(X) else np.asarray(X)
        save_embedding(outbase, E, case_ids, {"method": "identity", "dimensions": int(E.shape[1])})
        return E, None
    svd = TruncatedSVD(n_components=max_comp, random_state=random_state, n_iter=10)
    E = svd.fit_transform(X)
    meta = {
        "method": "TruncatedSVD",
        "dimensions": int(max_comp),
        "explained_variance_ratio_sum": float(np.sum(svd.explained_variance_ratio_)),
        "singular_values": [float(x) for x in svd.singular_values_],
    }
    save_embedding(outbase, E, case_ids, meta)
    if feature_names is not None:
        rows = []
        names = np.asarray(feature_names, dtype=object)
        for j, comp in enumerate(svd.components_):
            idx_pos = np.argsort(comp)[-20:][::-1]
            idx_neg = np.argsort(comp)[:20]
            rows.append({
                "component": j,
                "positive_features": " | ".join(str(names[i]) for i in idx_pos),
                "negative_features": " | ".join(str(names[i]) for i in idx_neg),
            })
        write_csv(pd.DataFrame(rows), outbase.with_name(outbase.name + "_component_loadings.csv"))
    return E, svd


def _fit_text_view(case_ids, docs: pd.Series, outdir: Path, view_name: str, *, word=True, char=True, max_word=60000, max_char=50000):
    outdir.mkdir(parents=True, exist_ok=True)
    registry = []
    docs = docs.fillna("").astype(str).map(normalize_text_for_similarity)
    n = len(docs)
    min_df = max(5, int(math.ceil(n * 0.001)))

    if word:
        vec = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 3),
            min_df=min_df,
            max_df=0.95,
            max_features=max_word,
            sublinear_tf=True,
            strip_accents="unicode",
            token_pattern=r"(?u)\b[^\W_][\w$.-]{1,}\b",
        )
        try:
            X = vec.fit_transform(docs)
        except ValueError:
            vec.set_params(min_df=2, max_df=1.0)
            try:
                X = vec.fit_transform(docs)
            except ValueError:
                X = None
        if X is None or X.shape[1] == 0:
            return registry
        names = vec.get_feature_names_out()
        base = outdir / f"{view_name}__word"
        save_sparse(base, X, np.asarray(case_ids), names, {
            "view": view_name, "representation": "word_tfidf_1_3gram", "min_df": min_df,
            "max_features": max_word, "shape": list(X.shape),
        })
        _svd_embedding(X, np.asarray(case_ids), outdir / f"{view_name}__word_svd", 128, names)
        registry.append({"view": f"{view_name}__word", "source_view": view_name, "matrix": str(base.name), "rows": X.shape[0], "features": X.shape[1], "kind": "sparse_tfidf"})

    if char:
        vec = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=min_df,
            max_df=0.98,
            max_features=max_char,
            sublinear_tf=True,
        )
        try:
            X = vec.fit_transform(docs)
        except ValueError:
            vec.set_params(min_df=2, max_df=1.0)
            try:
                X = vec.fit_transform(docs)
            except ValueError:
                X = None
        if X is None or X.shape[1] == 0:
            return registry
        names = vec.get_feature_names_out()
        base = outdir / f"{view_name}__char"
        save_sparse(base, X, np.asarray(case_ids), names, {
            "view": view_name, "representation": "char_tfidf_3_5gram", "min_df": min_df,
            "max_features": max_char, "shape": list(X.shape),
        })
        _svd_embedding(X, np.asarray(case_ids), outdir / f"{view_name}__char_svd", 96, names)
        registry.append({"view": f"{view_name}__char", "source_view": view_name, "matrix": str(base.name), "rows": X.shape[0], "features": X.shape[1], "kind": "sparse_char_tfidf"})
    return registry


def stage_structured(runroot: Path) -> None:
    out = runroot / "03_views" / "structured"
    out.mkdir(parents=True, exist_ok=True)
    df = load_frame(runroot / "01_raw" / "case_scalar_features")
    case_ids = df["case_id"].to_numpy()

    # Generic schema-driven feature classification.
    excluded = {"case_id", "repo_id", "issue_id", "pr_id"}
    numeric = []
    categorical = []
    freq_encoded = []
    audit = []

    for c in df.columns:
        if c in excluded:
            audit.append({"feature": c, "role": "identifier_grouping", "nunique": int(df[c].nunique(dropna=True))})
            continue
        if is_identifier_name(c):
            audit.append({"feature": c, "role": "excluded_identifier", "nunique": int(df[c].nunique(dropna=True))})
            continue
        if is_text_name(c):
            audit.append({"feature": c, "role": "excluded_raw_text", "nunique": int(df[c].nunique(dropna=True))})
            continue
        if is_time_name(c) and not pd.api.types.is_numeric_dtype(df[c]):
            audit.append({"feature": c, "role": "excluded_raw_timestamp", "nunique": int(df[c].nunique(dropna=True))})
            continue

        s = df[c]
        nun = int(s.nunique(dropna=True))
        if pd.api.types.is_numeric_dtype(s):
            numeric.append(c)
            audit.append({"feature": c, "role": "numeric", "nunique": nun})
        elif nun <= 100:
            categorical.append(c)
            audit.append({"feature": c, "role": "categorical_onehot", "nunique": nun})
        else:
            # High-cardinality objective categories become a generic frequency encoding only.
            freq_encoded.append(c)
            audit.append({"feature": c, "role": "high_cardinality_frequency", "nunique": nun})

    write_csv(pd.DataFrame(audit), out / "structured_feature_audit.csv")

    work = df[["case_id", "repo_id"] + numeric + categorical + freq_encoded].copy()
    for c in freq_encoded:
        vc = work[c].value_counts(dropna=False, normalize=True)
        work[c + "__value_frequency"] = work[c].map(vc).astype(float)
        numeric.append(c + "__value_frequency")
    work = work.drop(columns=freq_encoded, errors="ignore")

    # Automatic redundancy audit among numeric columns. Redundant variables are retained in raw data but pruned from the view.
    kept = []
    red = []
    for c in numeric:
        s = pd.to_numeric(work[c], errors="coerce")
        if s.notna().sum() < 10 or s.nunique(dropna=True) <= 1:
            red.append({"feature": c, "reason": "constant_or_too_sparse", "representative": ""})
            continue
        representative = None
        for k in kept:
            a = s; b = pd.to_numeric(work[k], errors="coerce")
            m = a.notna() & b.notna()
            if m.sum() < 30:
                continue
            rho = a[m].corr(b[m], method="spearman")
            if pd.notna(rho) and abs(rho) >= 0.985:
                representative = k
                break
        if representative:
            red.append({"feature": c, "reason": "abs_spearman_ge_0_985", "representative": representative})
        else:
            kept.append(c)
    write_csv(pd.DataFrame(red), out / "redundancy_pruning.csv")
    numeric = kept

    # Add missing indicators for numeric columns with missingness.
    for c in list(numeric):
        if work[c].isna().any():
            miss = c + "__missing"
            work[miss] = work[c].isna().astype(int)
            numeric.append(miss)

    transformers = []
    if numeric:
        transformers.append((
            "num",
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("scale", RobustScaler(with_centering=True, with_scaling=True)),
            ]),
            numeric,
        ))
    if categorical:
        transformers.append((
            "cat",
            Pipeline([
                ("impute", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=True, min_frequency=2)),
            ]),
            categorical,
        ))

    ct = ColumnTransformer(transformers, sparse_threshold=1.0, remainder="drop")
    X = ct.fit_transform(work)
    if not sparse.issparse(X):
        X = sparse.csr_matrix(X)
    try:
        names = ct.get_feature_names_out()
    except Exception:
        names = np.asarray([f"f{i}" for i in range(X.shape[1])])

    base = out / "structured_matrix"
    save_sparse(base, X, case_ids, names, {"numeric": numeric, "categorical": categorical, "shape": list(X.shape)})
    _svd_embedding(X, case_ids, out / "structured_svd", 128, names)
    save_frame(work[["case_id", "repo_id"] + numeric], out / "numeric_model_features")
    write_json(out / "STATUS.json", {"status": "OK", "rows": len(df), "matrix_features": int(X.shape[1]), "numeric": len(numeric), "categorical": len(categorical)})


def stage_text_views(runroot: Path) -> None:
    out = runroot / "03_views" / "text"
    out.mkdir(parents=True, exist_ok=True)
    text = load_frame(runroot / "01_raw" / "case_text")
    ids = text["case_id"].to_numpy()
    fields = [c for c in text.columns if c != "case_id"]
    registry = []
    field_stats = []
    valid_fields = []
    for c in fields:
        docs = text[c].fillna("").astype(str)
        nonempty = int((docs.str.strip().str.len() > 0).sum())
        field_stats.append({"field": c, "nonempty": nonempty, "median_chars": float(docs.str.len().median()), "nunique": int(docs.nunique())})
        if nonempty >= max(50, int(0.02 * len(docs))):
            valid_fields.append(c)
            registry.extend(_fit_text_view(ids, docs, out, c.replace("__", "_"), word=True, char=True))
    if valid_fields:
        combined = text[valid_fields].fillna("").astype(str).agg("\n".join, axis=1)
        registry.extend(_fit_text_view(ids, combined, out, "all_text", word=True, char=True, max_word=80000, max_char=60000))
    write_csv(pd.DataFrame(field_stats), out / "text_field_stats.csv")
    write_csv(pd.DataFrame(registry), out / "VIEW_REGISTRY.csv")
    write_json(out / "STATUS.json", {"status": "OK", "fields_considered": len(fields), "fields_vectorized": len(valid_fields), "views": len(registry)})


def stage_path_views(runroot: Path) -> None:
    out = runroot / "03_views" / "paths"
    out.mkdir(parents=True, exist_ok=True)
    files = load_frame(runroot / "01_raw" / "pr_files_with_patch")
    ids = load_frame(runroot / "01_raw" / "cases_linkage")["case_id"].to_numpy()
    filename_col = next((c for c in files.columns if c.lower() == "filename"), None)
    if not filename_col:
        raise RuntimeError("PR_FILES_FILENAME_COLUMN_MISSING")

    docs = []
    rawdocs = []
    metrics = []
    for cid in ids:
        g = files[files["case_id"] == cid]
        names = g[filename_col].dropna().astype(str).tolist()
        toks = list(itertools.chain.from_iterable(path_tokens(x) for x in names))
        docs.append(" ".join(toks))
        rawdocs.append("\n".join(names))
        segs = [str(x).replace("\\", "/").strip("/").split("/") for x in names]
        depths = [len(x) for x in segs if x]
        metrics.append({
            "case_id": cid,
            "path_file_count": len(names),
            "path_token_count": len(toks),
            "path_unique_token_count": len(set(toks)),
            "path_mean_depth": float(np.mean(depths)) if depths else np.nan,
            "path_max_depth": int(max(depths)) if depths else 0,
            "path_top_directory_share": float(pd.Series([x[0] for x in segs if x]).value_counts(normalize=True).iloc[0]) if any(segs) else np.nan,
        })
    save_frame(pd.DataFrame(metrics), out / "path_metrics")

    vec = TfidfVectorizer(token_pattern=r"(?u)\S+", lowercase=False, min_df=max(3, int(len(ids)*0.001)), max_df=0.98, max_features=80000, sublinear_tf=True)
    X = vec.fit_transform(docs)
    names = vec.get_feature_names_out()
    save_sparse(out / "path_token_tfidf", X, ids, names, {"representation": "automatically tokenized path segments/extensions/depths", "shape": list(X.shape)})
    _svd_embedding(X, ids, out / "path_token_svd", 128, names)

    cvec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,6), min_df=max(3, int(len(ids)*0.001)), max_df=0.99, max_features=60000, sublinear_tf=True)
    C = cvec.fit_transform(rawdocs)
    cnames = cvec.get_feature_names_out()
    save_sparse(out / "path_char_tfidf", C, ids, cnames, {"representation": "raw_path_char_ngrams", "shape": list(C.shape)})
    _svd_embedding(C, ids, out / "path_char_svd", 96, cnames)

    # Binary item matrix for later generic co-occurrence mining.
    bvec = CountVectorizer(token_pattern=r"(?u)\S+", lowercase=False, min_df=max(3, int(len(ids)*0.001)), max_features=100000, binary=True)
    B = bvec.fit_transform(docs)
    save_sparse(out / "path_items_binary", B, ids, bvec.get_feature_names_out(), {"representation": "binary_path_items"})
    write_csv(pd.DataFrame([
        {"view": "path_token", "kind": "sparse_tfidf", "features": X.shape[1]},
        {"view": "path_char", "kind": "sparse_char_tfidf", "features": C.shape[1]},
        {"view": "path_items", "kind": "binary_items", "features": B.shape[1]},
    ]), out / "VIEW_REGISTRY.csv")


def _parse_patch(patch: str):
    added = []
    removed = []
    hunks = []
    current = []
    in_hunk = False
    context = 0
    for line in str(patch or "").splitlines():
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = []
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added.append(line[1:])
            current.append("+")
        elif line.startswith("-"):
            removed.append(line[1:])
            current.append("-")
        else:
            context += 1
            current.append("=")
    if current:
        hunks.append(current)
    return added, removed, hunks, context


def _runs(seq):
    if not seq:
        return []
    out=[]; cur=seq[0]; n=1
    for x in seq[1:]:
        if x == cur:
            n += 1
        else:
            out.append((cur,n)); cur=x; n=1
    out.append((cur,n))
    return out


def stage_patch_views(runroot: Path) -> None:
    out = runroot / "03_views" / "patch"
    out.mkdir(parents=True, exist_ok=True)
    files = load_frame(runroot / "01_raw" / "pr_files_with_patch")
    cases = load_frame(runroot / "01_raw" / "cases_linkage")
    ids = cases["case_id"].to_numpy()
    patch_col = next((c for c in files.columns if c.lower() == "patch"), None)
    filename_col = next((c for c in files.columns if c.lower() == "filename"), None)
    if not patch_col:
        raise RuntimeError("PATCH_COLUMN_MISSING_IN_PR_FILES")

    rows = []
    docs = {"add_raw": [], "del_raw": [], "add_norm": [], "del_norm": [], "edit_shape": []}
    for cid in ids:
        g = files[files["case_id"] == cid]
        all_add=[]; all_del=[]; all_hunks=[]; context=0; per_file_changed=[]
        file_patch_count=0
        for _, r in g.iterrows():
            p = r.get(patch_col)
            if pd.isna(p) or not str(p).strip():
                continue
            file_patch_count += 1
            a,d,h,c = _parse_patch(str(p))
            all_add.extend(a); all_del.extend(d); all_hunks.extend(h); context += c
            per_file_changed.append(len(a)+len(d))
        raw_add = "\n".join(all_add)
        raw_del = "\n".join(all_del)
        toks_add = list(itertools.chain.from_iterable(codeish_tokenize(x, normalize_identifiers=False) for x in all_add))
        toks_del = list(itertools.chain.from_iterable(codeish_tokenize(x, normalize_identifiers=False) for x in all_del))
        norm_add = list(itertools.chain.from_iterable(codeish_tokenize(x, normalize_identifiers=True) for x in all_add))
        norm_del = list(itertools.chain.from_iterable(codeish_tokenize(x, normalize_identifiers=True) for x in all_del))

        shape_tokens=[]; add_runs=[]; del_runs=[]; replace_hunks=0
        for h in all_hunks:
            compact = "".join(h)
            shape_tokens.append("hseq=" + compact[:120])
            rs = _runs(h)
            for op,n in rs:
                bucket = min(20, int(n))
                shape_tokens.append(f"run={op}{bucket}")
                if op == "+": add_runs.append(n)
                elif op == "-": del_runs.append(n)
            if "+" in h and "-" in h:
                replace_hunks += 1
        docs["add_raw"].append(raw_add)
        docs["del_raw"].append(raw_del)
        docs["add_norm"].append(" ".join(norm_add))
        docs["del_norm"].append(" ".join(norm_del))
        docs["edit_shape"].append(" ".join(shape_tokens))

        changed = len(all_add)+len(all_del)
        arr = np.asarray(per_file_changed, dtype=float)
        shares = arr/arr.sum() if arr.size and arr.sum()>0 else np.asarray([])
        rows.append({
            "case_id": cid,
            "patch_files_with_content": file_patch_count,
            "patch_hunk_count": len(all_hunks),
            "patch_added_lines": len(all_add),
            "patch_removed_lines": len(all_del),
            "patch_context_lines": context,
            "patch_total_edited_lines": changed,
            "patch_add_fraction": len(all_add)/changed if changed else np.nan,
            "patch_replace_hunk_fraction": replace_hunks/len(all_hunks) if all_hunks else np.nan,
            "patch_max_add_run": max(add_runs) if add_runs else 0,
            "patch_max_del_run": max(del_runs) if del_runs else 0,
            "patch_raw_add_token_count": len(toks_add),
            "patch_raw_del_token_count": len(toks_del),
            "patch_unique_add_token_ratio": len(set(toks_add))/len(toks_add) if toks_add else np.nan,
            "patch_unique_del_token_ratio": len(set(toks_del))/len(toks_del) if toks_del else np.nan,
            "patch_top_file_edit_share": float(shares.max()) if shares.size else np.nan,
            "patch_file_edit_entropy": float(-(shares*np.log2(shares)).sum()) if shares.size else np.nan,
            "patch_mean_added_line_length": float(np.mean([len(x) for x in all_add])) if all_add else np.nan,
            "patch_mean_removed_line_length": float(np.mean([len(x) for x in all_del])) if all_del else np.nan,
        })
    metrics = pd.DataFrame(rows)
    save_frame(metrics, out / "patch_morphology")
    docs_df = pd.DataFrame({"case_id": ids, **docs})
    save_frame(docs_df, out / "patch_documents")

    registry=[]
    # Raw code lexical views: word and char. Normalized views intentionally remove identifier/literal semantics.
    registry += _fit_text_view(ids, pd.Series(docs["add_raw"]), out, "patch_add_raw", word=True, char=True, max_word=100000, max_char=80000)
    registry += _fit_text_view(ids, pd.Series(docs["del_raw"]), out, "patch_del_raw", word=True, char=True, max_word=100000, max_char=80000)

    for name in ["add_norm", "del_norm"]:
        vec = TfidfVectorizer(token_pattern=r"(?u)\S+", lowercase=False, ngram_range=(1,5), min_df=max(3, int(len(ids)*0.001)), max_df=0.99, max_features=100000, sublinear_tf=True)
        X = vec.fit_transform(docs[name])
        fn = vec.get_feature_names_out()
        base = out / f"patch_{name}_tfidf"
        save_sparse(base, X, ids, fn, {"representation": "generic_normalized_code_token_ngrams", "shape": list(X.shape)})
        _svd_embedding(X, ids, out / f"patch_{name}_svd", 128, fn)
        registry.append({"view": f"patch_{name}", "kind": "normalized_code_token_tfidf", "features": X.shape[1]})

    svec = TfidfVectorizer(token_pattern=r"(?u)\S+", lowercase=False, ngram_range=(1,3), min_df=max(3, int(len(ids)*0.001)), max_features=50000)
    S = svec.fit_transform(docs["edit_shape"])
    sn = svec.get_feature_names_out()
    save_sparse(out / "edit_shape_tfidf", S, ids, sn, {"representation": "unified_diff_operation_sequence_ngrams", "shape": list(S.shape)})
    _svd_embedding(S, ids, out / "edit_shape_svd", 64, sn)
    registry.append({"view": "edit_shape", "kind": "diff_operation_tfidf", "features": S.shape[1]})
    write_csv(pd.DataFrame(registry), out / "VIEW_REGISTRY.csv")


def _try_get_parser(language: str):
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser(language), "tree_sitter_language_pack"
    except Exception:
        pass
    try:
        from tree_sitter_languages import get_parser
        return get_parser(language), "tree_sitter_languages"
    except Exception:
        return None, "unavailable"


EXT_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript", ".tsx": "tsx",
    ".java": "java", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".hpp": "cpp",
    ".cs": "c_sharp", ".rb": "ruby", ".php": "php", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala", ".sh": "bash", ".sql": "sql", ".vue": "vue", ".html": "html", ".css": "css", ".json": "json",
}


def _walk_node_types(root, max_nodes=50000):
    c=Counter(); errors=0; total=0; stack=[root]
    while stack and total < max_nodes:
        n=stack.pop(); total += 1
        typ=str(getattr(n,"type","UNKNOWN")); c[typ]+=1
        if typ == "ERROR" or getattr(n,"is_error",False): errors += 1
        try:
            stack.extend(reversed(list(n.children)))
        except Exception:
            pass
    return c, total, errors


def _fallback_type_tokens(text: str):
    toks=codeish_tokenize(text, normalize_identifiers=False); out=[]
    for t in toks:
        if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", t): out.append("IDENT")
        elif re.match(r"^(0x[0-9A-Fa-f]+|\d+(?:\.\d+)?)$", t): out.append("NUMBER")
        elif len(t) <= 3 and re.search(r"[^A-Za-z0-9_$]", t): out.append("OP="+t)
        else: out.append("TOKEN")
    return out


def stage_syntax_views(runroot: Path) -> None:
    out = runroot / "03_views" / "syntax"
    out.mkdir(parents=True, exist_ok=True)
    files = load_frame(runroot / "01_raw" / "pr_files_with_patch")
    cases = load_frame(runroot / "01_raw" / "cases_linkage")
    ids = cases["case_id"].to_numpy()
    patch_col = next((c for c in files.columns if c.lower() == "patch"), None)
    filename_col = next((c for c in files.columns if c.lower() == "filename"), None)
    if not patch_col or not filename_col:
        raise RuntimeError("SYNTAX_REQUIRES_FILENAME_AND_PATCH")

    parser_cache={}
    add_docs=[]; del_docs=[]; metrics=[]; language_rows=[]
    for cid in ids:
        g=files[files["case_id"]==cid]
        add_types=[]; del_types=[]; parsed_files=0; fallback_files=0; error_nodes=0; total_nodes=0
        langs=Counter()
        for _,r in g.iterrows():
            p=r.get(patch_col); fn=str(r.get(filename_col) or "")
            if pd.isna(p) or not str(p).strip(): continue
            ext=Path(fn).suffix.lower(); lang=EXT_LANG.get(ext)
            a,d,_,_=_parse_patch(str(p)); at="\n".join(a); dt="\n".join(d)
            if lang:
                if lang not in parser_cache: parser_cache[lang]=_try_get_parser(lang)
                parser,provider=parser_cache[lang]
            else:
                parser=None; provider="unknown_extension"
            if parser is not None:
                parsed_files += 1; langs[lang]+=1
                for text,target in [(at,add_types),(dt,del_types)]:
                    if not text.strip(): continue
                    try:
                        tree=parser.parse(text.encode("utf-8",errors="replace"))
                        cnt,n,e=_walk_node_types(tree.root_node)
                        total_nodes += n; error_nodes += e
                        for typ,num in cnt.items(): target.extend([f"node={typ}"]*min(num,200))
                    except Exception:
                        fallback_files += 1; target.extend(_fallback_type_tokens(text))
            else:
                fallback_files += 1
                add_types.extend(_fallback_type_tokens(at)); del_types.extend(_fallback_type_tokens(dt))
        add_docs.append(" ".join(add_types)); del_docs.append(" ".join(del_types))
        metrics.append({
            "case_id":cid,"syntax_parsed_files":parsed_files,"syntax_fallback_files":fallback_files,
            "syntax_total_nodes":total_nodes,"syntax_error_nodes":error_nodes,
            "syntax_error_fraction":error_nodes/total_nodes if total_nodes else np.nan,
            "syntax_distinct_languages":len(langs),
        })
        for lang,n in langs.items(): language_rows.append({"case_id":cid,"language":lang,"parsed_files":n})
    save_frame(pd.DataFrame(metrics),out/"syntax_metrics")
    write_csv(pd.DataFrame(language_rows),out/"syntax_language_coverage.csv")
    registry=[]
    for name,docs in [("syntax_add",add_docs),("syntax_del",del_docs)]:
        vec=TfidfVectorizer(token_pattern=r"(?u)\S+",lowercase=False,ngram_range=(1,4),min_df=max(3,int(len(ids)*0.001)),max_features=80000,sublinear_tf=True)
        X=vec.fit_transform(docs); fn=vec.get_feature_names_out()
        save_sparse(out/f"{name}_tfidf",X,ids,fn,{"representation":"tree_sitter_node_type_or_generic_token_type_ngrams","shape":list(X.shape)})
        _svd_embedding(X,ids,out/f"{name}_svd",96,fn)
        registry.append({"view":name,"kind":"syntax_type_tfidf","features":X.shape[1]})
    write_csv(pd.DataFrame(registry),out/"VIEW_REGISTRY.csv")
    providers={lang:provider for lang,(parser,provider) in parser_cache.items()}
    write_json(out/"STATUS.json",{"status":"OK","parser_providers":providers,"cases":len(ids),"parsed_file_cases":int((pd.DataFrame(metrics)["syntax_parsed_files"]>0).sum())})
