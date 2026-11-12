#!/bin/bash
#SBATCH --job-name=t2xret
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_SYMMETRIC_X_RETRIEVAL_v1_%j.out

set -euo pipefail

GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import shutil
import sqlite3
import subprocess
import tarfile
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
GROUP = int(os.environ["GROUP"])
if GROUP not in (0, 1):
    raise SystemExit("GROUP must be 0 or 1")

DB = Path("/home-mscluster/astrauss/new/malicious-issue-miner-rate-smart/data/miner.agentic-js.eval.20260720_224159.hf-snapshot-20260817.db")
ROOTS_CSV = ROOT / "D7_FINAL_M_ROOTS_233_WITH_COHORTS.csv"
SEALED_MAPS = [
    ROOT / "T2_MECHANISM_OPPORTUNITY_CENSUS_v1_G0_SEALED_MAP.json",
    ROOT / "T2_MECHANISM_OPPORTUNITY_CENSUS_v1_G1_SEALED_MAP.json",
]

ALL_TARGETS = json.loads(r"""[{"root_id": "CROOT-00704-01", "workflow_cluster": "CROOT-00704", "candidate_id": "N-afbc2e017c", "stratum": "D2_CROSS_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_VERSION_CONSTRAINT"}, {"root_id": "CROOT-06104-01", "workflow_cluster": "CROOT-06104", "candidate_id": "N-6f3e546986", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "ADAPTER_INTEGRATION_IDENTIFIER"}, {"root_id": "CROOT-06104-02", "workflow_cluster": "CROOT-06104", "candidate_id": "N-cbd1a14e91", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "ADAPTER_HEALTH_STATE"}, {"root_id": "CROOT-06104-03", "workflow_cluster": "CROOT-06104", "candidate_id": "N-6d07033769", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "ADAPTER_RUNTIME_STATE"}, {"root_id": "CROOT-07930-01", "workflow_cluster": "CROOT-07930", "candidate_id": "N-6e59f23916", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "SAME_TASK_PROXY_FORWARDING"}, {"root_id": "CROOT-09998-01", "workflow_cluster": "CROOT-09998", "candidate_id": "N-b13325de50", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "SESSION_CONTINUITY_RESUME"}, {"root_id": "CROOT-10155-01", "workflow_cluster": "CROOT-10155", "candidate_id": "N-1c74dfc35a", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "SESSION_ROTATION_IDENTITY"}, {"root_id": "CROOT-10326-01", "workflow_cluster": "CROOT-10326", "candidate_id": "N-7dd76ea258", "stratum": "D2_CROSS_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "CLI_AUTH_SOURCE_REUSE"}, {"root_id": "CROOT-12344-01", "workflow_cluster": "CROOT-12344", "candidate_id": "N-0904d460a1", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "BYOK_CONFIG_VALIDATION"}, {"root_id": "CROOT-15703-01", "workflow_cluster": "CROOT-15703", "candidate_id": "N-4a3d0e6779", "stratum": "D2_CROSS_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_VERSION_UPDATE"}, {"root_id": "CROOT-16209-01", "workflow_cluster": "CROOT-16209", "candidate_id": "N-d80eec58ac", "stratum": "D1_SAME_REPO", "analysis_stratum": "PRIMARY_CANDIDATE", "abstract_opportunity_family": "SAME_TASK_HTTP_CONTAINER_HEADERS"}, {"root_id": "CROOT-00704-01", "workflow_cluster": "CROOT-00704", "candidate_id": "N-9e00650685", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_UPDATE_BROADER"}, {"root_id": "CROOT-00708-01", "workflow_cluster": "CROOT-00708", "candidate_id": "N-fa3b1ce701", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_SPEC_BROADER"}, {"root_id": "CROOT-00708-05", "workflow_cluster": "CROOT-00708", "candidate_id": "N-b510021022", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_SPEC_MISSING_DEP"}, {"root_id": "CROOT-03429-01", "workflow_cluster": "CROOT-03429", "candidate_id": "N-3acc8fe6a1", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "GENERATED_OUTPUT_WRITE_SURFACE"}, {"root_id": "CROOT-03622-01", "workflow_cluster": "CROOT-03622", "candidate_id": "N-46a1c77a4a", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_COMPATIBILITY_POSSIBLE"}, {"root_id": "CROOT-03684-01", "workflow_cluster": "CROOT-03684", "candidate_id": "N-f309aded4f", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "PLUGIN_ROOT_CONFIG_SURFACE"}, {"root_id": "CROOT-08461-01", "workflow_cluster": "CROOT-08461", "candidate_id": "N-730763930d", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "MARKDOWN_TEXT_TRANSFORM_BROADER"}, {"root_id": "CROOT-10361-01", "workflow_cluster": "CROOT-10361", "candidate_id": "N-94b7c58ee5", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "SFTP_FILE_LIFECYCLE"}, {"root_id": "CROOT-10361-02", "workflow_cluster": "CROOT-10361", "candidate_id": "N-2bfce5b043", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "SFTP_FILE_LIFECYCLE"}, {"root_id": "CROOT-10361-03", "workflow_cluster": "CROOT-10361", "candidate_id": "N-7259d9a513", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "SFTP_FILE_LIFECYCLE"}, {"root_id": "CROOT-12344-01", "workflow_cluster": "CROOT-12344", "candidate_id": "N-8ed5defd55", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "AUTH_VALIDATION_PROBE_BROADER"}, {"root_id": "CROOT-12898-01", "workflow_cluster": "CROOT-12898", "candidate_id": "N-853fb42317", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "GENERATED_BUILD_ARTIFACT_WRITE"}, {"root_id": "CROOT-13922-01", "workflow_cluster": "CROOT-13922", "candidate_id": "N-43595561fe", "stratum": "D1_SAME_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "SETTINGS_PATH_FILE_MANAGEMENT"}, {"root_id": "CROOT-15703-01", "workflow_cluster": "CROOT-15703", "candidate_id": "N-bda32c243a", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "DEPENDENCY_SPEC_PEER_DEPENDENCY"}, {"root_id": "CROOT-16213-01", "workflow_cluster": "CROOT-16213", "candidate_id": "N-b112f5222a", "stratum": "D2_CROSS_REPO", "analysis_stratum": "SENSITIVITY_CANDIDATE", "abstract_opportunity_family": "LOCAL_SESSION_STORAGE_LIFECYCLE"}]""")
ALL_TARGETS = sorted(ALL_TARGETS, key=lambda x: (x["workflow_cluster"], x["root_id"], x["candidate_id"]))
TARGETS = [x for i, x in enumerate(ALL_TARGETS) if i % 2 == GROUP]

OUT = ROOT / f"T2_SYMMETRIC_X_RETRIEVAL_v1_G{GROUP}"
BLIND = ROOT / f"T2_SYMMETRIC_X_RETRIEVAL_v1_G{GROUP}_BLIND_REVIEW.tar.gz"
SEALED = ROOT / f"T2_SYMMETRIC_X_RETRIEVAL_v1_G{GROUP}_SEALED.tar.gz"
TMP = Path(os.environ.get("SLURM_TMPDIR", "/tmp")) / f"t2_xret_g{GROUP}"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
TMP.mkdir(parents=True, exist_ok=True)

for p in [DB, ROOTS_CSV, *SEALED_MAPS]:
    if not p.exists():
        raise SystemExit(f"MISSING_REQUIRED_INPUT={p}")

EXPECTED_ROOTS_SHA = "83e23d84dd572219fca5817588a91d1cc668f76178759b6430825fa590ee9573"

def sha256(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

actual_roots_sha = sha256(ROOTS_CSV)
if actual_roots_sha != EXPECTED_ROOTS_SHA:
    raise SystemExit(f"ROOTS_CSV_SHA_MISMATCH actual={actual_roots_sha} expected={EXPECTED_ROOTS_SHA}")

SOURCE_EXTS = {
    ".js",".jsx",".ts",".tsx",".mjs",".cjs",".py",".go",".rs",".java",".kt",".kts",
    ".cs",".cpp",".cc",".c",".h",".hpp",".rb",".php",".swift",".scala",".sh",".bash",
    ".zsh",".vue",".svelte",".html",".css",".scss",".json",".yaml",".yml",".toml",".xml"
}
SKIP_PARTS = {
    "node_modules","vendor","dist","build","coverage",".git","generated","fixtures","fixture",
    "__snapshots__","snapshots"
}
TEST_PARTS = {
    "test","tests","spec","specs","fixture","fixtures","mock","mocks","__tests__","benchmark","benchmarks"
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
    "source","target","time","timeout","process","context","support","update","change","issue"
}

MAX_TARGET_FILES = 5
MAX_QUERY_TERMS = 12
MAX_CANDIDATES = 24
MAX_FILE_BYTES = 350_000
SEARCH_TIMEOUT = 25
SEED = 20260921

def sh(args, cwd=None, timeout=None):
    p = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout, p.stderr

def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(s))[:180]

def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip())

def is_test_path(path):
    parts = [p.casefold() for p in Path(str(path or "")).parts]
    name = Path(str(path or "")).name.casefold()
    return any(p in TEST_PARTS for p in parts) or bool(re.search(r"(^|[._-])(test|spec)([._-]|$)", name))

def source_file(path):
    return Path(str(path or "")).suffix.casefold() in SOURCE_EXTS

def skip_path(path):
    parts = {p.casefold() for p in Path(str(path or "")).parts}
    return bool(parts & SKIP_PARTS)

def added_lines(diff):
    return [ln[1:] for ln in str(diff or "").splitlines() if ln.startswith("+") and not ln.startswith("+++")]

def mechanism_terms(diff, root_summary, family):
    text = "\n".join(added_lines(diff)) + "\n" + str(root_summary or "") + "\n" + str(family or "")
    score = Counter()

    calls = re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]{2,})\s*\(", text)
    strings = [m.group(1).strip() for m in re.finditer(r"""['"]([^'"\n]{4,80})['"]""", text)]
    words = re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$-]{3,}\b", text)

    def ok(t):
        q = t.casefold()
        if q in STOP or q.isdigit():
            return False
        return len(q) >= 5

    for t in calls:
        if ok(t):
            score[t] += 6
    for t in strings:
        if ok(t) and len(t) <= 60:
            score[t] += 5
    for t in words:
        if ok(t):
            score[t] += 2
    for t in re.split(r"[_\s-]+", str(family or "")):
        if ok(t):
            score[t] += 4

    ranked = sorted(score, key=lambda t: (-score[t], -len(t), t.casefold()))
    return ranked[:MAX_QUERY_TERMS]

def line_snippet(content, line_no, radius=18):
    lines = content.splitlines()
    if not lines:
        return ""
    i = max(0, int(line_no) - 1)
    a = max(0, i - radius)
    b = min(len(lines), i + radius + 1)
    return "\n".join(f"{j+1:6d}: {lines[j]}" for j in range(a, b))

def fetch_repo(repo, stored_base, stored_head, workdir):
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    sh(["git","init","-q"], cwd=workdir)
    sh(["git","remote","add","origin",f"https://github.com/{repo}.git"], cwd=workdir)
    for sha in [stored_base, stored_head]:
        rc, so, se = sh(["git","fetch","-q","--filter=blob:none","--no-tags","origin",sha], cwd=workdir, timeout=1200)
        if rc != 0:
            raise RuntimeError(f"fetch failed for stored commit: {se[-1200:]}")
    rc, mb, se = sh(["git","merge-base",stored_base,stored_head], cwd=workdir, timeout=300)
    if rc != 0 or not mb.strip():
        raise RuntimeError(f"merge-base failed: {se[-1200:]}")
    return mb.strip(), stored_head

def changed_files(repo_dir, base, head):
    rc, out, err = sh(["git","diff","--name-only",base,head,"--"], cwd=repo_dir, timeout=300)
    if rc != 0:
        raise RuntimeError(f"changed-files diff failed: {err[-1000:]}")
    return [x.strip() for x in out.splitlines() if x.strip()]

def diff_for(repo_dir, base, head, targets):
    if not targets:
        return ""
    rc, out, err = sh(["git","diff","--unified=6",base,head,"--",*targets], cwd=repo_dir, timeout=300)
    return out if rc == 0 else ""

def git_show(repo_dir, base, path):
    rc, out, err = sh(["git","show",f"{base}:{path}"], cwd=repo_dir, timeout=180)
    return out if rc == 0 else None

def scopes_for(targets):
    local = []
    parent = []
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
    return local[:6], parent[:6]

def search_prebase(repo_dir, base, targets, terms):
    target_set = set(targets)
    target_dirs = {str(Path(p).parent) for p in targets}
    target_exts = {Path(p).suffix.casefold() for p in targets}
    local_scopes, parent_scopes = scopes_for(targets)

    candidates = {}
    stats = {
        "terms": terms,
        "local_scopes": local_scopes,
        "parent_scopes": parent_scopes,
        "grep_calls": 0,
        "grep_timeouts": 0,
        "grep_errors": 0,
    }

    for term in terms:
        term_hits = 0
        scopes = [(s, "local") for s in local_scopes] + [(s, "parent") for s in parent_scopes]
        for scope, kind in scopes:
            if term_hits >= 40:
                break
            stats["grep_calls"] += 1
            try:
                rc, out, err = sh(
                    ["git","grep","-n","-I","-F","-e",term,base,"--",scope],
                    cwd=repo_dir,
                    timeout=SEARCH_TIMEOUT,
                )
            except subprocess.TimeoutExpired:
                stats["grep_timeouts"] += 1
                continue
            if rc not in (0, 1):
                stats["grep_errors"] += 1
                continue

            for line in out.splitlines():
                if term_hits >= 40:
                    break
                m = re.match(r"^[^:]+:(.*?):(\d+):(.*)$", line)
                if not m:
                    continue
                path = m.group(1)
                ln = int(m.group(2))
                if skip_path(path) or not source_file(path):
                    continue
                key = (path, ln)
                d = candidates.setdefault(key, {"path":path,"line":ln,"terms":set(),"score":0.0})
                d["terms"].add(term)
                d["score"] += 1.0
                if kind == "local":
                    d["score"] += 1.0
                if str(Path(path).parent) in target_dirs:
                    d["score"] += 1.0
                if Path(path).suffix.casefold() in target_exts:
                    d["score"] += 0.3
                if path not in target_set:
                    d["score"] += 1.5
                term_hits += 1

    rows = []
    for d in candidates.values():
        d["score"] += 0.8 * (len(d["terms"]) - 1)
        rows.append(d)
    rows.sort(key=lambda x: (x["score"], len(x["terms"]), x["path"], -x["line"]), reverse=True)

    selected = []
    per_file = Counter()
    for d in rows:
        if len(selected) >= MAX_CANDIDATES:
            break
        if per_file[d["path"]] >= 4:
            continue
        content = git_show(repo_dir, base, d["path"])
        if content is None or len(content.encode("utf-8", errors="ignore")) > MAX_FILE_BYTES:
            continue
        selected.append({
            "path": d["path"],
            "line": d["line"],
            "score": round(d["score"], 3),
            "matched_terms": sorted(d["terms"]),
            "is_target_file": d["path"] in target_set,
            "snippet": line_snippet(content, d["line"]),
        })
        per_file[d["path"]] += 1

    stats["candidate_count"] = len(selected)
    stats["non_target_candidate_count"] = sum(not x["is_target_file"] for x in selected)
    return selected, stats

with ROOTS_CSV.open(newline="", encoding="utf-8-sig") as f:
    root_rows = {r["root_id"]: r for r in csv.DictReader(f)}

sealed_map = {}
for p in SEALED_MAPS:
    obj = json.loads(p.read_text(encoding="utf-8"))
    for cid, val in obj.items():
        if cid in sealed_map:
            raise SystemExit(f"DUPLICATE_CANDIDATE_ID={cid}")
        sealed_map[cid] = val

for t in TARGETS:
    cid = t["candidate_id"]
    if cid not in sealed_map:
        raise SystemExit(f"CANDIDATE_NOT_IN_SEALED_MAP={cid}")
    if sealed_map[cid]["root_id"] != t["root_id"]:
        raise SystemExit(f"ROOT_MISMATCH candidate={cid}")

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
con.row_factory = sqlite3.Row
DB_LOCK = threading.Lock()
issue_cols = {r[1] for r in con.execute('PRAGMA table_info("issues")')}
issue_body_expr = "i.body AS issue_body" if "body" in issue_cols else "'' AS issue_body"

def case_row(case_id):
    with DB_LOCK:
        row = con.execute(f"""
            SELECT c.id AS case_id,c.repo_id,r.full_name AS repository,
                   i.number AS issue_number,i.title AS issue_title,{issue_body_expr},
                   p.id AS pr_id,p.number AS pr_number,p.base_sha,p.head_sha
            FROM cases c
            JOIN repos r ON r.id=c.repo_id
            JOIN issues i ON i.id=c.issue_id
            JOIN pull_requests p ON p.id=c.pr_id
            WHERE c.id=?
        """, (int(case_id),)).fetchone()
    return dict(row) if row else None

def pr_files(pr_id):
    with DB_LOCK:
        rows = con.execute(
            "SELECT filename,patch,status,additions,deletions FROM pr_files WHERE pr_id=?",
            (int(pr_id),)
        ).fetchall()
    return [dict(r) for r in rows]

def introduced_findings(case_id):
    with DB_LOCK:
        rows = con.execute(
            "SELECT scanner,rule_id,file_path,line,description,introduced FROM scanner_findings WHERE case_id=? AND introduced=1",
            (int(case_id),)
        ).fetchall()
    return [dict(r) for r in rows]

def scanner_ok(case_id, scanner):
    with DB_LOCK:
        row = con.execute(
            "SELECT 1 FROM scanner_runs WHERE case_id=? AND scanner=? AND status='ok' LIMIT 1",
            (int(case_id),scanner)
        ).fetchone()
    return bool(row)

def choose_positive_targets(root, pos, files):
    summary = str(root.get("root_summary") or "")
    finds = introduced_findings(pos["case_id"])
    paths = []
    for f in finds:
        fp = str(f.get("file_path") or "")
        if fp and (fp in summary or Path(fp).name in summary):
            paths.append(fp)
    if not paths:
        for f in finds:
            fp = str(f.get("file_path") or "")
            if fp:
                paths.append(fp)

    valid = [p for p in paths if any(str(x.get("filename") or "") == p for x in files)]
    if not valid:
        valid = [
            str(x.get("filename") or "") for x in files
            if not is_test_path(x.get("filename"))
            and source_file(x.get("filename"))
            and Path(str(x.get("filename") or "")).name in summary
        ]
    if not valid:
        valid = [
            str(x.get("filename") or "") for x in files
            if not is_test_path(x.get("filename")) and source_file(x.get("filename"))
        ]
    return list(dict.fromkeys(valid))[:MAX_TARGET_FILES]

def choose_negative_targets(files, positive_targets):
    pos_exts = {Path(p).suffix.casefold() for p in positive_targets}
    prod = [
        str(x.get("filename") or "") for x in files
        if not is_test_path(x.get("filename")) and source_file(x.get("filename"))
    ]
    same = [p for p in prod if Path(p).suffix.casefold() in pos_exts]
    return list(dict.fromkeys(same + prod))[:MAX_TARGET_FILES]

rng = random.Random(SEED)
blind_map = {}
for t in ALL_TARGETS:
    labs = ["A","B"]
    rng.shuffle(labs)
    blind_map[t["candidate_id"]] = {"positive": labs[0], "negative": labs[1]}

def process_pair(t):
    cid = t["candidate_id"]
    rid = t["root_id"]
    root = root_rows[rid]
    maprow = sealed_map[cid]

    pos_case = int(root["case_id"])
    neg_case = int(maprow["negative_case_id"])
    pos = case_row(pos_case)
    neg = case_row(neg_case)
    if not pos or not neg:
        raise RuntimeError("case lookup failed")

    pfiles = pr_files(pos["pr_id"])
    nfiles = pr_files(neg["pr_id"])
    ptargets_hint = choose_positive_targets(root, pos, pfiles)
    ntargets_hint = choose_negative_targets(nfiles, ptargets_hint)

    pair_tmp = TMP / safe_name(cid)
    p_repo = pair_tmp / "P_REPO"
    n_repo = pair_tmp / "N_REPO"

    pbase, phead = fetch_repo(pos["repository"], str(pos["base_sha"]), str(pos["head_sha"]), p_repo)
    nbase, nhead = fetch_repo(neg["repository"], str(neg["base_sha"]), str(neg["head_sha"]), n_repo)

    pchanged = changed_files(p_repo, pbase, phead)
    nchanged = changed_files(n_repo, nbase, nhead)

    ptargets = [p for p in ptargets_hint if p in pchanged]
    if not ptargets:
        ptargets = [p for p in pchanged if not is_test_path(p) and source_file(p)][:MAX_TARGET_FILES]

    ntargets = [p for p in ntargets_hint if p in nchanged]
    if not ntargets:
        ntargets = [p for p in nchanged if not is_test_path(p) and source_file(p)][:MAX_TARGET_FILES]

    pdiff = diff_for(p_repo, pbase, phead, ptargets)
    terms = mechanism_terms(pdiff, root.get("root_summary",""), t.get("abstract_opportunity_family",""))

    pcands, pstats = search_prebase(p_repo, pbase, ptargets, terms)
    ncands, nstats = search_prebase(n_repo, nbase, ntargets, terms)

    relevant_scanners = sorted({
        str(x.get("scanner") or "") for x in introduced_findings(pos_case) if x.get("scanner")
    })
    neg_scanner_ok = all(scanner_ok(neg_case, s) for s in relevant_scanners) if relevant_scanners else False

    role_to_side = blind_map[cid]
    side_payloads = {}

    for role, case, targets, cands, stats in [
        ("positive", pos, ptargets, pcands, pstats),
        ("negative", neg, ntargets, ncands, nstats),
    ]:
        side = role_to_side[role]
        opaque = []
        sealed_candidates = []
        for i, c in enumerate(cands, 1):
            cand_id = f"{side}X-{i:02d}"
            path_token = hashlib.sha256(c["path"].encode()).hexdigest()[:10]
            opaque.append({
                "candidate_id": cand_id,
                "path_token": path_token,
                "score": c["score"],
                "matched_terms": c["matched_terms"],
                "is_target_file": c["is_target_file"],
                "snippet": c["snippet"],
            })
            sealed_candidates.append({"candidate_id": cand_id, **c})

        side_payloads[side] = {
            "issue_title": norm(case.get("issue_title","")),
            "issue_body_excerpt": norm(case.get("issue_body",""))[:1500],
            "target_file_count": len(targets),
            "candidate_count": len(cands),
            "non_target_candidate_count": sum(not x["is_target_file"] for x in cands),
            "search_stats": {
                "grep_calls": stats.get("grep_calls",0),
                "grep_timeouts": stats.get("grep_timeouts",0),
                "grep_errors": stats.get("grep_errors",0),
            },
            "candidates": opaque,
        }

        side_payloads[side + "_SEALED"] = {
            "role": role,
            "repository": case["repository"],
            "case_id": case["case_id"],
            "pr_number": case["pr_number"],
            "base_sha": pbase if role == "positive" else nbase,
            "head_sha": phead if role == "positive" else nhead,
            "target_files": targets,
            "candidates": sealed_candidates,
        }

    review = {
        "pair_id": cid,
        "root_id": rid,
        "workflow_cluster": t["workflow_cluster"],
        "analysis_stratum": t["analysis_stratum"],
        "match_stratum": t["stratum"],
        "abstract_opportunity_family": t["abstract_opportunity_family"],
        "frozen_M": norm(root.get("root_summary","")),
        "same_mechanism_query_terms": terms,
        "side_A": side_payloads["A"],
        "side_B": side_payloads["B"],
        "adjudication_template": {
            "same_implementation_opportunity_confirmed": None,
            "side_A_authentic_prechange_X_for_M": None,
            "side_B_authentic_prechange_X_for_M": None,
            "side_A_non_target_separable_X": None,
            "side_B_non_target_separable_X": None,
            "Xp_Xn_same_mechanism_class": None,
            "scanner_applicability_gate": None,
            "plus_minus_only_X_visibility_feasible": None,
            "decision": "UNADJUDICATED"
        }
    }

    sealed_rec = {
        "pair_id": cid,
        "root_id": rid,
        "positive_case_id": pos_case,
        "negative_case_id": neg_case,
        "positive_repository": pos["repository"],
        "negative_repository": neg["repository"],
        "blind_mapping": role_to_side,
        "negative_relevant_scanners_historically_ok": neg_scanner_ok,
        "positive_target_files": ptargets,
        "negative_target_files": ntargets,
        "same_mechanism_query_terms": terms,
        "side_A": side_payloads["A_SEALED"],
        "side_B": side_payloads["B_SEALED"],
    }
    return review, sealed_rec

reviews = []
sealed_records = []
errors = []

with ThreadPoolExecutor(max_workers=2) as ex:
    futures = {ex.submit(process_pair, t): t for t in TARGETS}
    for fut in as_completed(futures):
        t = futures[fut]
        try:
            review, sealed_rec = fut.result()
            reviews.append(review)
            sealed_records.append(sealed_rec)
            print(
                "PAIR_DONE",
                review["pair_id"],
                "A=", review["side_A"]["candidate_count"],
                "B=", review["side_B"]["candidate_count"],
                "A_NON_TARGET=", review["side_A"]["non_target_candidate_count"],
                "B_NON_TARGET=", review["side_B"]["non_target_candidate_count"],
                flush=True,
            )
        except Exception as e:
            errors.append({
                "pair_id": t["candidate_id"],
                "root_id": t["root_id"],
                "error": str(e)[:3000],
            })
            print("PAIR_FAIL", t["candidate_id"], str(e)[:1000], flush=True)

reviews.sort(key=lambda x: x["pair_id"])
sealed_records.sort(key=lambda x: x["pair_id"])

review_dir = OUT / "BLIND_REVIEW"
sealed_dir = OUT / "SEALED"
review_dir.mkdir()
sealed_dir.mkdir()

for r in reviews:
    (review_dir / f'{r["pair_id"]}.json').write_text(
        json.dumps(r, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )
for r in sealed_records:
    (sealed_dir / f'{r["pair_id"]}.json').write_text(
        json.dumps(r, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8"
    )

summary = {
    "version": "T2_SYMMETRIC_X_RETRIEVAL_v1",
    "group": GROUP,
    "targets_assigned": len(TARGETS),
    "pairs_pass": len(reviews),
    "pairs_fail": len(errors),
    "pairs_with_non_target_candidates_both_sides": sum(
        r["side_A"]["non_target_candidate_count"] > 0
        and r["side_B"]["non_target_candidate_count"] > 0
        for r in reviews
    ),
    "pairs_zero_candidates_any_side": sum(
        r["side_A"]["candidate_count"] == 0
        or r["side_B"]["candidate_count"] == 0
        for r in reviews
    ),
    "retrieval_method": (
        "v9-derived chronology-safe target-local + one-parent fixed-string search; "
        "the same frozen M-derived term set is applied to both sides; non-target files are prioritized."
    ),
    "blinding": (
        "positive/negative roles randomized to A/B; role mapping and exact repository/path/case identifiers "
        "remain sealed on cluster."
    ),
    "frozen_target_sha256": "1763ed6148edcb6763124ae682afff69701531415cc9666a3cdf5d04793d2cb0",
    "v9_source_archive_sha256": "46e784fe591662b6be6079e6d09885ce787309899d63d3a7d2c907801e927667",
}
(review_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
(sealed_dir / "ERRORS.json").write_text(json.dumps(errors, indent=2) + "\n", encoding="utf-8")

if BLIND.exists():
    BLIND.unlink()
if SEALED.exists():
    SEALED.unlink()

with tarfile.open(BLIND, "w:gz") as tf:
    tf.add(review_dir, arcname="BLIND_REVIEW")
with tarfile.open(SEALED, "w:gz") as tf:
    tf.add(sealed_dir, arcname="SEALED")

print("STATUS=DONE")
print("GROUP=", GROUP)
print("TARGETS=", len(TARGETS))
print("PAIRS_PASS=", len(reviews))
print("PAIRS_FAIL=", len(errors))
print("BOTH_HAVE_NON_TARGET_X_CANDIDATES=", summary["pairs_with_non_target_candidates_both_sides"])
print("ZERO_CANDIDATE_ANY_SIDE=", summary["pairs_zero_candidates_any_side"])
print("BLIND_REVIEW=", BLIND)
print("BLIND_SHA256=", sha256(BLIND))
print("SEALED_ON_CLUSTER=", SEALED)
print("SEALED_SHA256=", sha256(SEALED))
PY
