#!/bin/bash
#SBATCH --job-name=t1res3v10
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --array=0-2
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_RESERVE3_CONTEXT_EXPANDED_v10_%A_%a.out

ROOT="$HOME/research_artifacts"
SHARD="${SLURM_ARRAY_TASK_ID:?SLURM_ARRAY_TASK_ID missing}"
NSHARDS=3
OUT="$ROOT/T1_RESERVE3_CONTEXT_EXPANDED_v10_SHARD${SHARD}"
BLIND="$ROOT/T1_RESERVE3_CONTEXT_EXPANDED_v10_SHARD${SHARD}_BLINDED.tar.gz"
SEALED="$ROOT/T1_RESERVE3_CONTEXT_EXPANDED_v10_SHARD${SHARD}_SEALED_KEY.csv"
QCARCH="$ROOT/T1_RESERVE3_CONTEXT_EXPANDED_v10_SHARD${SHARD}_QC.tar.gz"

mkdir -p "$OUT"

python3 -u - "$ROOT" "$OUT" "$SEALED" "$SHARD" "$NSHARDS" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import zipfile
from collections import Counter, defaultdict

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
SEALED = Path(sys.argv[3]).resolve()
SHARD = int(sys.argv[4])
NSHARDS = int(sys.argv[5])
TMP = Path(os.environ.get("SLURM_TMPDIR", "/tmp")) / f"t1_primary29_context_census_v9_shard{SHARD}"
TMP.mkdir(parents=True, exist_ok=True)

SEED = 20260921
MAX_TARGET_FILES = 5
MAX_QUERY_TERMS = 10
MAX_GREP_HITS_PER_TERM = 80
MAX_CANDIDATES = 40
MAX_FILE_BYTES = 350_000
MAX_SNIPPET_LINES = 41
SEARCH_TIMEOUT_SECONDS = 45
MAX_GLOBAL_TERMS = 4

SOURCE_EXTS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".py", ".go", ".rs",
    ".java", ".kt", ".kts", ".cs", ".cpp", ".cc", ".c", ".h", ".hpp",
    ".rb", ".php", ".swift", ".scala", ".sh", ".bash", ".zsh", ".vue",
    ".svelte", ".html", ".css", ".scss", ".json", ".yaml", ".yml",
}

STOP = {
    "const","let","var","return","function","async","await","true","false","null","undefined",
    "this","that","from","with","then","else","while","for","if","try","catch","throw","new",
    "string","number","boolean","object","array","error","result","value","values","data","item",
    "items","config","options","params","request","response","test","tests","expect","describe","it",
    "import","export","default","class","public","private","protected","static","void","any","unknown",
    "src","app","lib","index","main","type","interface","props","state","set","get","use","create",
    "join","image","tobe","pipe","date","path","file","read","write","open","close","push","pop",
    "map","filter","find","match","replace","split","parse","stringify","route","method","client",
    "server","model","user","name","body","code","message","success","failure","before","after",
    "source","target","time","timeout","process","context",
}


def sh(args, cwd=None, timeout=None):
    p = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def norm(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").strip().lower()).strip("_")


def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s))[:180]


def extract_exact_archive_member(archive: Path, filename: str):
    if not archive.exists():
        raise SystemExit(f"REQUIRED_INPUT_MISSING: {archive}")
    dst = TMP / "sources" / filename
    dst.parent.mkdir(parents=True, exist_ok=True)
    if archive.name.endswith('.tar.gz'):
        with tarfile.open(archive, 'r:gz') as t:
            members = [m for m in t.getmembers() if m.isfile() and Path(m.name).name == filename]
            if len(members) != 1:
                raise SystemExit(f"EXPECTED_ONE_MEMBER:{filename}:found={len(members)} in {archive}")
            f = t.extractfile(members[0])
            dst.write_bytes(f.read())
            return dst
    if archive.suffix == '.zip':
        with zipfile.ZipFile(archive) as z:
            members = [m for m in z.namelist() if Path(m).name == filename]
            if len(members) != 1:
                raise SystemExit(f"EXPECTED_ONE_MEMBER:{filename}:found={len(members)} in {archive}")
            dst.write_bytes(z.read(members[0]))
            return dst
    raise SystemExit(f"UNSUPPORTED_INPUT_ARCHIVE: {archive}")

STEP6_ARCHIVE = ROOT / "DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz"
DB_PATH = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")

print(f"SOURCE_CHECK step6={STEP6_ARCHIVE} exists={STEP6_ARCHIVE.exists()}", flush=True)

STEP6 = extract_exact_archive_member(STEP6_ARCHIVE, "STEP6_UNBLINDED_PAIRS_51.csv")

sources = {"step6_51": STEP6}
(OUT / "SOURCE_LOCATIONS.json").write_text(
    json.dumps({k: str(v) if v else None for k,v in sources.items()}, indent=2) + "\n"
)
print("SOURCE_LOAD_OK", flush=True)

def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))

step6_rows = read_csv(STEP6)
if len(step6_rows) != 51:
    raise SystemExit(f"EXPECTED_51_STEP6_ROWS:found={len(step6_rows)}")

headers = {"step6_51": list(step6_rows[0].keys()) if step6_rows else []}
(OUT / "SOURCE_HEADERS.json").write_text(json.dumps(headers, indent=2) + "\n")

def select_primary31(rows):
    chosen = [r for r in rows if str(r.get("analysis_role", "")).strip().upper() == "PRIMARY"]
    if len(chosen) != 31:
        raise SystemExit(f"PRIMARY_SELECTION_FAIL expected=31 found={len(chosen)}")
    tiers = Counter(str(r.get("match_tier", "")).strip() for r in chosen)
    if tiers != Counter({"D1_SAME_REPO": 22, "D2_EXISTING_C2_WORKFLOW": 9}):
        raise SystemExit(f"PRIMARY_TIER_QC_FAIL {dict(tiers)}")
    return chosen, {"method": "analysis_role_PRIMARY", "key": "analysis_role", "tiers": dict(tiers)}

primary_rows, primary_selection = select_primary31(step6_rows)
print(
    f"PRIMARY_SELECTION_OK count={len(primary_rows)} tiers={primary_selection['tiers']}",
    flush=True,
)

def pair_id_of(row):
    for k,v in row.items():
        nk = norm(k)
        sv = str(v or "").strip()
        if "pair" in nk and ("id" in nk or re.fullmatch(r"s5pair_?\d+", norm(sv))):
            if sv:
                return sv
    for v in row.values():
        sv = str(v or "").strip()
        if re.fullmatch(r"S5PAIR-\d+", sv, flags=re.I):
            return sv.upper()
    return None


# Two PRIMARY pairs cannot be mapped uniquely back to a single historical
# control workflow from the frozen Step-6 package + frozen DB. Exclude them
# for provenance integrity rather than guessing a PR after the fact.
EXCLUDED_SOURCE_AMBIGUITY = {
    "S5PAIR-033": {
        "role": "control",
        "source_id": "CTRL-F34DED9BF7",
        "candidate_case_ids": [7679, 7681],
        "reason": (
            "Frozen Step-6 identifies the decision but does not retain the exact "
            "control case/PR mapping. Both DB candidates share the exact repo, "
            "issue title, focal file, and a readFileSync filesystem-I/O change."
        ),
    },
    "S5PAIR-047": {
        "role": "control",
        "source_id": "CTRL-F364CFEB9D",
        "candidate_case_ids": [34278, 34279, 34280, 34281],
        "reason": (
            "Frozen Step-6 identifies the decision but does not retain the exact "
            "control case/PR mapping. Multiple DB candidates share the exact repo "
            "and issue title, and three modify the focal test file."
        ),
    },
}

selected_primary_rows = list(primary_rows)
excluded_rows = [
    {
        "pair_id": pair_id_of(r),
        **EXCLUDED_SOURCE_AMBIGUITY[pair_id_of(r)],
    }
    for r in selected_primary_rows
    if pair_id_of(r) in EXCLUDED_SOURCE_AMBIGUITY
]
primary_rows = [
    r for r in selected_primary_rows
    if pair_id_of(r) not in EXCLUDED_SOURCE_AMBIGUITY
]

if len(selected_primary_rows) != 31 or len(primary_rows) != 29 or len(excluded_rows) != 2:
    raise SystemExit(
        f"AMBIGUITY_EXCLUSION_QC_FAIL selected={len(selected_primary_rows)} "
        f"included={len(primary_rows)} excluded={len(excluded_rows)}"
    )

(OUT / "PRE_CENSUS_EXCLUSIONS.json").write_text(
    json.dumps(
        {
            "rule": (
                "Exclude only pairs whose exact historical control workflow "
                "cannot be uniquely recovered from frozen Step-6 + frozen DB. "
                "No scanner or experimental outcome is used."
            ),
            "selected_primary_pairs": 31,
            "included_pairs": 29,
            "excluded_pairs": excluded_rows,
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print(
    "CENSUS_COHORT_OK selected=31 included=29 excluded=2 "
    "excluded_pair_ids=['S5PAIR-033','S5PAIR-047']",
    flush=True,
)

# Preserve the exact v7 A/B randomization independently of sharding.
all_primary_rows_sorted = sorted(primary_rows, key=lambda r: pair_id_of(r) or "")
rng_for_mapping = random.Random(SEED)
global_blind_mapping = {}
for _row in all_primary_rows_sorted:
    _pid = pair_id_of(_row)
    _labels = ["A", "B"]
    rng_for_mapping.shuffle(_labels)
    global_blind_mapping[_pid] = {
        "positive": _labels[0],
        "control": _labels[1],
    }

# v10 pilot-extension cohort: exactly the three pre-frozen reserve pairs.
# One array worker per pair; no outcome-based selection occurs here.
TARGET_PAIR_IDS = ["S5PAIR-012", "S5PAIR-022", "S5PAIR-049"]
if SHARD < 0 or SHARD >= len(TARGET_PAIR_IDS):
    raise SystemExit(f"INVALID_SHARD {SHARD}")
target_pair_id = TARGET_PAIR_IDS[SHARD]
primary_rows = [row for row in all_primary_rows_sorted if pair_id_of(row) == target_pair_id]
if len(primary_rows) != 1:
    raise SystemExit(f"TARGET_PAIR_SELECTION_FAIL pair={target_pair_id} found={len(primary_rows)}")
EXPECTED_SIDES = 2
print(f"RESERVE3_SELECTION_OK shard={SHARD} pair={target_pair_id}", flush=True)

print(
    f"SHARD_SELECTION_OK shard={SHARD}/{NSHARDS} "
    f"pairs={len(primary_rows)} sides={EXPECTED_SIDES} "
    f"pair_ids={[pair_id_of(r) for r in primary_rows]}",
    flush=True,
)

def side_meta(pair_row, side):
    prefix = "positive" if side == "positive" else "control"
    file_path = str(pair_row.get(f"{prefix}_file_path", "") or "").strip()
    return {
        "repo": str(pair_row.get(f"{prefix}_repository", "") or "").strip(),
        "issue_title": str(pair_row.get(f"{prefix}_issue_title", "") or "").strip(),
        "source_id": str(pair_row.get(f"{prefix}_source_id", "") or "").strip(),
        "decision_summary": str(pair_row.get(f"{prefix}_decision_summary", "") or "").strip(),
        "mechanism_summary": str(pair_row.get(f"{prefix}_mechanism_summary", "") or "").strip(),
        "decision_family": str(pair_row.get("decision_family", "") or "").strip(),
        "issue_text": str(pair_row.get(f"{prefix}_issue_title", "") or "").strip(),
        "paths_from_metadata": [file_path] if file_path else [],
    }


def title_norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip()).casefold()


def resolve_side_in_db(con, meta):
    repo = meta.get("repo") or ""
    title = meta.get("issue_title") or ""
    path = (meta.get("paths_from_metadata") or [""])[0]

    base_select = """
        SELECT DISTINCT
            c.id AS case_id,
            r.full_name AS repository,
            i.number AS issue_number,
            i.title AS issue_title,
            p.number AS pr_number,
            p.url AS pr_url,
            p.base_sha AS stored_base_sha,
            p.head_sha AS stored_head_sha
        FROM cases c
        JOIN repos r ON r.id = c.repo_id
        JOIN issues i ON i.id = c.issue_id
        JOIN pull_requests p ON p.id = c.pr_id
    """

    pf_cols = {r[1] for r in con.execute('PRAGMA table_info("pr_files")')}
    if "previous_filename" in pf_cols:
        file_clause = "(pf.filename=? OR pf.previous_filename=?)"
        file_params = (path, path)
    else:
        file_clause = "pf.filename=?"
        file_params = (path,)

    q1 = base_select + f"""
        WHERE lower(r.full_name)=lower(?)
          AND i.title=?
          AND EXISTS (
              SELECT 1 FROM pr_files pf
              WHERE pf.pr_id=c.pr_id
                AND {file_clause}
          )
    """
    rows = con.execute(q1, (repo, title, *file_params)).fetchall()
    if len(rows) == 1:
        return dict(rows[0]), "repo_exact_title_file"

    q2 = base_select + """
        WHERE lower(r.full_name)=lower(?)
          AND i.title=?
    """
    rows2 = con.execute(q2, (repo, title)).fetchall()
    if len(rows2) == 1:
        return dict(rows2[0]), "repo_exact_title_unique"

    q3 = base_select + """
        WHERE lower(r.full_name)=lower(?)
    """
    repo_rows = con.execute(q3, (repo,)).fetchall()
    normalized = [r for r in repo_rows if title_norm(r["issue_title"]) == title_norm(title)]
    if len(normalized) == 1:
        return dict(normalized[0]), "repo_normalized_title_unique"

    return None, {
        "repo": repo,
        "issue_title": title,
        "file_path": path,
        "exact_title_file_matches": len(rows),
        "exact_title_matches": len(rows2),
        "normalized_title_matches": len(normalized),
        "candidate_case_ids": [int(r["case_id"]) for r in normalized[:20]],
    }

def fetch_repo(repo, stored_base_sha, stored_head_sha, cache):
    key=safe_name(repo)
    repo_dir=cache/key
    if not (repo_dir/".git").exists():
        if repo_dir.exists(): shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True)
        sh(["git","init","-q"],cwd=repo_dir)
        sh(["git","remote","add","origin",f"https://github.com/{repo}.git"],cwd=repo_dir)

    for sha in [stored_base_sha, stored_head_sha]:
        rc,so,se=sh(["git","fetch","-q","--filter=blob:none","--no-tags","origin",sha],cwd=repo_dir,timeout=1200)
        if rc!=0:
            raise RuntimeError(f"commit fetch failed {sha}: {se[-2000:]}")

    rc,mb,se=sh(["git","merge-base",stored_base_sha,stored_head_sha],cwd=repo_dir,timeout=300)
    if rc!=0 or not mb.strip():
        raise RuntimeError(f"merge-base failed: {se[-2000:]}")
    base=mb.strip()
    return repo_dir, base, stored_head_sha, "db_stored_base_head_true_merge_base"

def git_show(repo_dir, rev, path):
    rc,out,err=sh(["git","show",f"{rev}:{path}"],cwd=repo_dir,timeout=180)
    if rc!=0:
        return None
    return out


def changed_files(repo_dir, base, head):
    rc,out,err=sh(["git","diff","--name-only",base,head,"--"],cwd=repo_dir,timeout=300)
    if rc!=0:
        return []
    return [x.strip() for x in out.splitlines() if x.strip()]


def choose_targets(meta, changed):
    exact=[]
    for p in meta.get("paths_from_metadata",[]):
        if p in changed and p not in exact:
            exact.append(p)
        else:
            for c in changed:
                if c.endswith("/"+p) or p.endswith("/"+c):
                    if c not in exact: exact.append(c)
    if exact:
        return exact[:MAX_TARGET_FILES]
    source=[p for p in changed if Path(p).suffix.lower() in SOURCE_EXTS]
    return (source or changed)[:MAX_TARGET_FILES]


def diff_for(repo_dir,base,head,targets):
    args=["git","diff","--unified=6",base,head,"--"]+targets
    rc,out,err=sh(args,cwd=repo_dir,timeout=300)
    return out if rc==0 else ""


def added_lines(diff):
    xs=[]
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            xs.append(line[1:])
    return xs


def query_terms(diff, summary):
    text = "\n".join(added_lines(diff)) + "\n" + (summary or "")

    # Prefer concrete calls / distinctive literals over generic identifiers.
    calls = re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]{2,})\s*\(", text)
    identifiers = re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]{3,}\b", text)
    strings = []
    for m in re.finditer(r"['\"]([^'\"\n]{4,80})['\"]", text):
        val = m.group(1).strip()
        if re.fullmatch(r"[A-Za-z0-9_./:@?&=+ \-]+", val):
            strings.append(val)

    score = Counter()

    def acceptable(t):
        lt = t.casefold()
        if lt in STOP or lt.isdigit():
            return False
        # Short all-lowercase words are usually catastrophic grep terms.
        distinctive = (
            len(t) >= 8
            or "_" in t
            or "-" in t
            or "." in t
            or "/" in t
            or any(ch.isupper() for ch in t[1:])
        )
        return distinctive

    for t in calls:
        if acceptable(t):
            score[t] += 5
    for t in identifiers:
        if acceptable(t):
            score[t] += 2
    for t in strings:
        if acceptable(t):
            score[t] += 4

    ranked = sorted(score, key=lambda t: (-score[t], -len(t), t.casefold()))
    return ranked[:MAX_QUERY_TERMS]

def line_snippet(content,line_no,radius=20):
    lines=content.splitlines()
    if not lines: return ""
    i=max(0,int(line_no)-1)
    a=max(0,i-radius); b=min(len(lines),i+radius+1)
    return "\n".join(f"{j+1:6d}: {lines[j]}" for j in range(a,b))


def _search_scopes(targets):
    local = []
    parent = []
    grandparent = []

    for target in targets:
        p = Path(target)
        d = str(p.parent)
        if d not in ("", ".") and d not in local:
            local.append(d)
        elif str(p) not in local:
            local.append(str(p))

        pd = str(p.parent.parent)
        if pd not in ("", ".") and pd != d and pd not in parent:
            parent.append(pd)

        gd = str(p.parent.parent.parent)
        if gd not in ("", ".") and gd not in (d, pd) and gd not in grandparent:
            grandparent.append(gd)

    return local[:8], parent[:8], grandparent[:8]


def search_prebase(repo_dir, base, targets, terms):
    candidates = {}
    target_dirs = {str(Path(p).parent) for p in targets}
    target_exts = {Path(p).suffix.lower() for p in targets}
    local_scopes, parent_scopes, grandparent_scopes = _search_scopes(targets)

    stats = {
        "terms": list(terms),
        "local_scopes": local_scopes,
        "parent_scopes": parent_scopes,
        "grandparent_scopes": grandparent_scopes,
        "global_terms_attempted": [],
        "grep_calls": 0,
        "grep_timeouts": 0,
        "grep_errors": 0,
    }

    def absorb(term, out, scope_kind):
        added = 0
        for line in out.splitlines():
            if added >= MAX_GREP_HITS_PER_TERM:
                break
            m = re.match(r"^[^:]+:(.*?):(\d+):(.*)$", line)
            if not m:
                continue
            path = m.group(1)
            ln = int(m.group(2))
            line_text = m.group(3)
            low = path.lower()
            if any(seg in low for seg in [
                "node_modules/", "vendor/", "dist/", "build/", "coverage/",
                ".min.", "/generated/", "/fixtures/", "/snapshots/"
            ]):
                continue
            if Path(path).suffix.lower() not in SOURCE_EXTS:
                continue

            key = (path, ln)
            d = candidates.setdefault(key, {
                "path": path,
                "line": ln,
                "line_text": line_text,
                "terms": set(),
                "scope_kinds": set(),
                "score": 0.0,
            })
            d["terms"].add(term)
            d["scope_kinds"].add(scope_kind)
            d["score"] += 1.0
            if scope_kind == "local": d["score"] += 1.2
            elif scope_kind == "parent": d["score"] += 0.8
            elif scope_kind == "grandparent": d["score"] += 0.5
            elif scope_kind == "global": d["score"] += 0.1
            if str(Path(path).parent) in target_dirs: d["score"] += 1.0
            if Path(path).suffix.lower() in target_exts: d["score"] += 0.4
            if path in targets: d["score"] -= 2.0  # keep target evidence, but prefer separable context X
            added += 1
        return added

    for term_index, term in enumerate(terms):
        term_hits = 0
        scopes = ([(s, "local") for s in local_scopes] +
                  [(s, "parent") for s in parent_scopes] +
                  [(s, "grandparent") for s in grandparent_scopes])

        for scope, scope_kind in scopes:
            stats["grep_calls"] += 1
            try:
                rc, out, err = sh(
                    ["git", "grep", "-n", "-I", "-F", "-e", term, base, "--", scope],
                    cwd=repo_dir,
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                stats["grep_timeouts"] += 1
                continue
            if rc not in (0, 1):
                stats["grep_errors"] += 1
                continue
            term_hits += absorb(term, out, scope_kind)
            if term_hits >= 20:
                break

        # Symmetric repository-wide fallback only for the strongest few terms
        # and only when scoped retrieval did not already provide enough hits.
        if term_index < MAX_GLOBAL_TERMS and term_hits < 6:
            stats["global_terms_attempted"].append(term)
            stats["grep_calls"] += 1
            try:
                rc, out, err = sh(
                    ["git", "grep", "-n", "-I", "-F", "-e", term, base, "--"],
                    cwd=repo_dir,
                    timeout=SEARCH_TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                stats["grep_timeouts"] += 1
                continue
            if rc not in (0, 1):
                stats["grep_errors"] += 1
                continue
            absorb(term, out, "global")

    rows = []
    for d in candidates.values():
        d["score"] += 0.8 * (len(d["terms"]) - 1)
        rows.append(d)

    # Prefer independent/non-target precedent so Context- never requires deleting
    # historical repository code. Target-local evidence remains available for audit.
    rows.sort(
        key=lambda x: (
            x["path"] not in targets,
            x["score"],
            len(x["terms"]),
            x["path"],
            -x["line"],
        ),
        reverse=True,
    )

    selected = []
    per_file = Counter()
    target_selected = 0
    for d in rows:
        if len(selected) >= MAX_CANDIDATES:
            break
        if per_file[d["path"]] >= 5:
            continue
        if d["path"] in targets and target_selected >= 2:
            continue

        content = git_show(repo_dir, base, d["path"])
        if content is None or len(content.encode("utf-8", errors="ignore")) > MAX_FILE_BYTES:
            continue

        selected.append({
            "path": d["path"],
            "line": d["line"],
            "score": round(d["score"], 3),
            "matched_terms": sorted(d["terms"]),
            "scope_kinds": sorted(d["scope_kinds"]),
            "is_target_file": d["path"] in targets,
            "snippet": line_snippet(content, d["line"]),
        })
        per_file[d["path"]] += 1
        if d["path"] in targets:
            target_selected += 1

    stats["candidate_count"] = len(selected)
    stats["non_target_candidate_count"] = sum(not x["is_target_file"] for x in selected)
    stats["target_candidate_count"] = sum(x["is_target_file"] for x in selected)
    return selected, stats

def write_side_packet(pair_dir, blind_side, meta, resolved, raw_pair):
    sd=pair_dir/blind_side
    sd.mkdir(parents=True,exist_ok=True)
    public_meta={
        "pair_id": pair_dir.name,
        "side": blind_side,
        "repository": meta.get("repo"),
        "pr_number": meta.get("pr"),
        "case_id": meta.get("case_id"),
        "decision_family": meta.get("decision_family"),
        "decision_summary": meta.get("decision_summary"),
        "issue_text_if_available": meta.get("issue_text"),
        "base_sha": resolved.get("base_sha"),
        "head_sha": resolved.get("head_sha"),
        "base_resolution_source": resolved.get("base_resolution_source"),
        "target_files": resolved.get("target_files",[]),
        "query_terms": resolved.get("query_terms",[]),
        "search_stats": resolved.get("search_stats",{}),
        "extraction_status": resolved.get("status"),
        "extraction_note": resolved.get("note","")
    }
    (sd/"PACKET_METADATA.json").write_text(json.dumps(public_meta,indent=2)+"\n",encoding="utf-8")
    if resolved.get("historical_diff") is not None:
        (sd/"HISTORICAL_DECISION_CONTEXT.diff").write_text(resolved["historical_diff"],encoding="utf-8")
    base_context=resolved.get("base_context",{})
    for i,(path,content) in enumerate(base_context.items(),1):
        (sd/f"BASE_TARGET_{i:02d}_{safe_name(path)}.txt").write_text(f"PATH: {path}\n\n{content}",encoding="utf-8")
    (sd/"PRECHANGE_REPO_SEARCH_CANDIDATES.json").write_text(json.dumps(resolved.get("candidates",[]),indent=2)+"\n",encoding="utf-8")


cache=TMP/"repos"; cache.mkdir(parents=True,exist_ok=True)

if not DB_PATH.exists():
    raise SystemExit(f"DB_MISSING: {DB_PATH}")
con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
con.row_factory = sqlite3.Row

# Resolve this shard's included sides against the frozen 3,809-workflow database BEFORE any network/repository work.
resolution = {}
resolution_errors = []
for idx,row in enumerate(sorted(primary_rows,key=lambda r: pair_id_of(r) or ""),1):
    pid = pair_id_of(row) or f"PAIR-{idx:03d}"
    for role in ["positive","control"]:
        meta = side_meta(row, role)
        resolved_row, method = resolve_side_in_db(con, meta)
        if resolved_row is None:
            resolution_errors.append({"pair_id":pid,"role":role,"source_id":meta.get("source_id"),"diagnostic":method})
        else:
            resolution[(pid,role)] = {**resolved_row, "resolution_method": method}

(OUT/"SOURCE_RESOLUTION_ERRORS.json").write_text(json.dumps(resolution_errors,indent=2)+"\n",encoding="utf-8")
if resolution_errors or len(resolution) != EXPECTED_SIDES:
    print(f"SOURCE_RESOLUTION_FAIL resolved={len(resolution)} errors={len(resolution_errors)}", flush=True)
    for e in resolution_errors[:20]:
        print(json.dumps(e, sort_keys=True), flush=True)
    raise SystemExit(7)

method_counts = Counter(v["resolution_method"] for v in resolution.values())
print(f"SOURCE_RESOLUTION_OK sides={len(resolution)} methods={dict(method_counts)}", flush=True)

sealed_rows=[]
index_rows=[]
errors=[]
status_counts=Counter()

# Deterministic order by pair ID, then randomize side labels with frozen seed.
primary_rows_sorted=sorted(primary_rows,key=lambda r: pair_id_of(r) or "")

for idx,row in enumerate(primary_rows_sorted,1):
    pid=pair_id_of(row) or f"PAIR-{idx:03d}"
    print(f"PAIR_START shard={SHARD} {idx}/{len(primary_rows_sorted)} {pid}", flush=True)
    pmeta=side_meta(row,"positive")
    nmeta=side_meta(row,"control")

    mapping = global_blind_mapping[pid]
    sealed_rows.append({"pair_id":pid,"side_A_role":"positive" if mapping["positive"]=="A" else "control",
                        "side_B_role":"positive" if mapping["positive"]=="B" else "control",
                        "positive_source_id":pmeta.get("source_id",""),"control_source_id":nmeta.get("source_id","")})

    pair_dir=OUT/"blinded_packets"/pid
    pair_dir.mkdir(parents=True,exist_ok=True)

    for role,meta in [("positive",pmeta),("control",nmeta)]:
        blind_side=mapping[role]
        dbrow = resolution[(pid, role)]
        meta["case_id"] = int(dbrow["case_id"])
        meta["pr"] = int(dbrow["pr_number"])
        meta["issue_number"] = int(dbrow["issue_number"])
        meta["stored_base_sha"] = str(dbrow["stored_base_sha"] or "")
        meta["stored_head_sha"] = str(dbrow["stored_head_sha"] or "")
        meta["source_resolution_method"] = dbrow["resolution_method"]

        # Resume support: keep any side already extracted successfully by an earlier attempt.
        side_dir = pair_dir / blind_side
        existing_meta_path = side_dir / "PACKET_METADATA.json"
        existing_cands_path = side_dir / "PRECHANGE_REPO_SEARCH_CANDIDATES.json"
        if existing_meta_path.exists() and existing_cands_path.exists():
            try:
                existing_meta = json.loads(existing_meta_path.read_text(encoding="utf-8"))
                existing_cands = json.loads(existing_cands_path.read_text(encoding="utf-8"))
            except Exception:
                existing_meta = {}
                existing_cands = []
            if existing_meta.get("extraction_status") == "PASS":
                status_counts["PASS"] += 1
                index_rows.append({
                    "pair_id":pid,
                    "blind_side":blind_side,
                    "repository":existing_meta.get("repository") or meta.get("repo") or "",
                    "pr_number":existing_meta.get("pr_number") or meta.get("pr") or "",
                    "case_id":existing_meta.get("case_id") or meta.get("case_id") or "",
                    "decision_family":existing_meta.get("decision_family") or meta.get("decision_family") or "",
                    "decision_summary":existing_meta.get("decision_summary") or meta.get("decision_summary") or "",
                    "extraction_status":"PASS",
                    "target_file_count":len(existing_meta.get("target_files") or []),
                    "candidate_count":len(existing_cands or []),
                    "base_resolution_source":existing_meta.get("base_resolution_source") or "",
                })
                continue

        resolved={"status":"NOT_RUN","note":"","base_context":{},"candidates":[]}
        try:
            if not meta.get("repo") or not meta.get("stored_base_sha") or not meta.get("stored_head_sha"):
                raise RuntimeError(f"metadata incomplete after DB resolution: repo={meta.get('repo')} base={meta.get('stored_base_sha')} head={meta.get('stored_head_sha')}")
            repo_dir,base,head,bsource=fetch_repo(meta["repo"],meta["stored_base_sha"],meta["stored_head_sha"],cache)
            ch=changed_files(repo_dir,base,head)
            targets=choose_targets(meta,ch)
            hist=diff_for(repo_dir,base,head,targets) if targets else ""
            term_source = (meta.get("decision_summary","") + "\n" + meta.get("mechanism_summary","")).strip()
            terms=query_terms(hist,term_source)
            bctx={}
            for p in targets:
                content=git_show(repo_dir,base,p)
                if content is not None:
                    if len(content.encode("utf-8",errors="ignore"))<=MAX_FILE_BYTES:
                        bctx[p]=content
                    else:
                        bctx[p]=content[:MAX_FILE_BYTES//2] + "\n\n[TRUNCATED]\n"
            cands, search_stats=search_prebase(repo_dir,base,targets,terms)
            resolved={
                "status":"PASS","note":"","base_sha":base,"head_sha":head,"base_resolution_source":bsource,
                "target_files":targets,"historical_diff":hist,"query_terms":terms,"base_context":bctx,
                "candidates":cands,"search_stats":search_stats,
            }
        except Exception as e:
            resolved={"status":"FAIL","note":str(e)[:3000],"base_context":{},"candidates":[]}
            errors.append({"pair_id":pid,"role":role,"error":str(e)[:3000],"meta":meta})
        status_counts[resolved["status"]]+=1
        write_side_packet(pair_dir,blind_side,meta,resolved,row)
        ss = resolved.get("search_stats", {})
        print(
            f"SIDE_DONE {pid} {blind_side} status={resolved['status']} "
            f"repo={meta.get('repo')} pr={meta.get('pr')} "
            f"candidates={len(resolved.get('candidates',[]))} "
            f"grep_calls={ss.get('grep_calls',0)} timeouts={ss.get('grep_timeouts',0)}",
            flush=True,
        )
        index_rows.append({
            "pair_id":pid,"blind_side":blind_side,"repository":meta.get("repo") or "","pr_number":meta.get("pr") or "",
            "case_id":meta.get("case_id") or "","decision_family":meta.get("decision_family") or "",
            "decision_summary":meta.get("decision_summary") or "","extraction_status":resolved.get("status"),
            "target_file_count":len(resolved.get("target_files",[])),"candidate_count":len(resolved.get("candidates",[])),
            "base_resolution_source":resolved.get("base_resolution_source","")
        })

# sealed key is deliberately outside blinded packet tree
with SEALED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["pair_id","side_A_role","side_B_role","positive_source_id","control_source_id"])
    w.writeheader(); w.writerows(sealed_rows)

with (OUT/"BLINDED_PACKET_INDEX.csv").open("w",newline="",encoding="utf-8") as f:
    fields=["pair_id","blind_side","repository","pr_number","case_id","decision_family","decision_summary","extraction_status","target_file_count","candidate_count","base_resolution_source"]
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(index_rows)

(OUT/"EXTRACTION_ERRORS.json").write_text(json.dumps(errors,indent=2)+"\n",encoding="utf-8")

protocol = {
    "schema":"T1_RESERVE3_CONTEXT_EXPANDED_v10",
    "population":"Three pre-frozen reserve pairs from the v9 blinded adjudication: S5PAIR-012, S5PAIR-022, S5PAIR-049; one array worker per pair",
    "shard":SHARD,
    "nshards":NSHARDS,
    "shard_pair_count":len(primary_rows),
    "shard_expected_sides":EXPECTED_SIDES,
    "primary_selection":primary_selection,
    "purpose":"symmetric expanded chronology-safe retrieval for the three pre-frozen reserve pairs before any LLM generation",
    "blinding":"positive/control roles randomized to A/B using frozen seed; scanner labels omitted from blinded packets",
    "seed":SEED,
    "retrieval":"same deterministic expanded procedure on both sides: target-local, parent, grandparent, then bounded repository-wide fallback for the strongest query terms; all snippets are read from the resolved pre-PR base only",
    "source_resolution":"each shard preflight-resolves all of its assigned sides against the frozen 3,809-workflow SQLite database using repository + exact issue title + focal file when available; no repository work starts in that shard unless every assigned side resolves uniquely",
    "candidate_search":"specificity-filtered fixed-string terms searched symmetrically in local, parent, grandparent scopes with bounded repository-wide fallback for up to four strongest terms; each grep is capped at 45 seconds; target-file hits are retained only for audit and non-target precedent is prioritized",
    "important_limit":"retrieval candidates are evidence packets, not labels. Presence of a search hit does not itself establish risky precedent or a safer alternative.",
    "next_annotation_fields":[
        "target_mechanism_precedent_present","precedent_strength","safer_local_alternative_present",
        "alternative_strength","decision_required_for_task","context_completeness","rationale_with_candidate_ids"
    ],
}
(OUT/"FROZEN_PROTOCOL.json").write_text(json.dumps(protocol,indent=2)+"\n",encoding="utf-8")

qc={
    "schema":"T1_RESERVE3_CONTEXT_EXPANDED_v10",
    "primary_rows_loaded":len(primary_rows),
    "shard":SHARD,
    "nshards":NSHARDS,
    "expected_sides_this_shard":EXPECTED_SIDES,
    "primary_rows_originally_selected":len(selected_primary_rows),
    "pre_census_excluded_pairs":excluded_rows,
    "primary_selection":primary_selection,
    "unique_pair_ids":len({pair_id_of(r) for r in primary_rows if pair_id_of(r)}),
    "blinded_sides":len(index_rows),
    "status_counts":dict(status_counts),
    "sealed_key_sha256":sha256(SEALED),
    "source_files":{k:(str(v) if v else None) for k,v in sources.items()},
    "database":str(DB_PATH),
    "source_resolution_methods":dict(method_counts),
    "source_sha256":{k:(sha256(v) if v and v.exists() else None) for k,v in sources.items()},
    "pass_condition":"exactly one of the three pre-frozen reserve pairs is assigned to each array worker; both sides use the identical expanded retrieval rule; extraction failures/timeouts are retained and never silently dropped",
    "shard":SHARD,
    "nshards":NSHARDS,
    "expected_sides_this_shard":EXPECTED_SIDES,
}
(OUT/"QC.json").write_text(json.dumps(qc,indent=2)+"\n",encoding="utf-8")
con.close()

checks=[]
for p in sorted((OUT/"blinded_packets").rglob("*")):
    if p.is_file(): checks.append(f"{sha256(p)}  {p.relative_to(OUT)}")
for p in [OUT/"BLINDED_PACKET_INDEX.csv",OUT/"FROZEN_PROTOCOL.json",OUT/"QC.json",OUT/"SOURCE_HEADERS.json",OUT/"SOURCE_LOCATIONS.json"]:
    if p.exists(): checks.append(f"{sha256(p)}  {p.relative_to(OUT)}")
(OUT/"SHA256SUMS.txt").write_text("\n".join(checks)+"\n",encoding="utf-8")

print(json.dumps(qc,indent=2))
print("STATUS=DONE")
PY
PYRC=$?

cd "$ROOT"

if [ "$PYRC" -ne 0 ]; then
  echo "PYTHON_FAILED rc=$PYRC"
  echo "No final archives created."
  rm -f "$BLIND" "$SEALED" "$QCARCH"
  exit "$PYRC"
fi

rm -f "$BLIND" "$QCARCH"

# Blinded bundle: safe to upload for coding; no role key.
tar -czf "$BLIND" \
  -C "$OUT" \
  blinded_packets \
  BLINDED_PACKET_INDEX.csv \
  FROZEN_PROTOCOL.json \
  QC.json \
  SOURCE_HEADERS.json \
  SOURCE_LOCATIONS.json \
  SHA256SUMS.txt

# QC bundle excludes cached repositories and contains extraction diagnostics.
tar -czf "$QCARCH" \
  -C "$OUT" \
  EXTRACTION_ERRORS.json \
  SOURCE_RESOLUTION_ERRORS.json \
  QC.json \
  SOURCE_HEADERS.json \
  SOURCE_LOCATIONS.json \
  FROZEN_PROTOCOL.json

echo
echo "=== OUTPUTS ==="
ls -lh "$BLIND" "$SEALED" "$QCARCH"
sha256sum "$BLIND" "$SEALED" "$QCARCH"
echo "STATUS=ARCHIVED"
