#!/bin/bash
#SBATCH --job-name=t1ctx31v4
#SBATCH --partition=bigbatch
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_PRIMARY31_CONTEXT_CENSUS_v4.out

ROOT="$HOME/research_artifacts"
OUT="$ROOT/T1_PRIMARY31_CONTEXT_CENSUS_v4"
BLIND="$ROOT/T1_PRIMARY31_CONTEXT_CENSUS_v4_BLINDED.tar.gz"
SEALED="$ROOT/T1_PRIMARY31_CONTEXT_CENSUS_v4_SEALED_KEY.csv"
QCARCH="$ROOT/T1_PRIMARY31_CONTEXT_CENSUS_v4_QC.tar.gz"

mkdir -p "$OUT"

python3 -u - "$ROOT" "$OUT" "$SEALED" <<'PY'
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from collections import Counter, defaultdict

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
SEALED = Path(sys.argv[3]).resolve()
TMP = Path(os.environ.get("SLURM_TMPDIR", "/tmp")) / "t1_primary31_context_census_v4"
TMP.mkdir(parents=True, exist_ok=True)

SEED = 20260921
MAX_TARGET_FILES = 5
MAX_QUERY_TERMS = 10
MAX_GREP_HITS_PER_TERM = 80
MAX_CANDIDATES = 24
MAX_FILE_BYTES = 350_000
MAX_SNIPPET_LINES = 41

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
    # Prefer an explicit D1/D2 match-tier column.
    diagnostics = {"columns": list(rows[0].keys()), "candidates": []}
    for key in rows[0].keys():
        nk = norm(key)
        vals = [str(r.get(key, "") or "").strip() for r in rows]
        upper = [v.upper() for v in vals]
        if "tier" in nk or "match" in nk:
            chosen = [r for r, v in zip(rows, upper) if v in {"D1", "D2"}]
            diagnostics["candidates"].append({
                "key": key, "method": "D1_D2", "count": len(chosen),
                "values": sorted(set(vals))[:30],
            })
            if len(chosen) == 31:
                return chosen, {"method": "D1_D2", "key": key}

    # Next prefer an explicit primary/cohort flag.
    trueish = {"primary", "yes", "true", "1", "d1/d2", "d1_d2", "d1d2"}
    falseish = {"sensitivity", "no", "false", "0", "d3/d4", "d3_d4", "d3d4"}
    for key in rows[0].keys():
        nk = norm(key)
        if not any(w in nk for w in ("primary", "cohort", "analysis_set", "set")):
            continue
        vals = [str(r.get(key, "") or "").strip() for r in rows]
        nvals = [norm(v) for v in vals]
        chosen = [r for r, v in zip(rows, nvals) if v in trueish]
        diagnostics["candidates"].append({
            "key": key, "method": "primary_flag", "count": len(chosen),
            "values": sorted(set(vals))[:30],
        })
        if len(chosen) == 31:
            return chosen, {"method": "primary_flag", "key": key}

    # Last schema-robust fallback: find any column whose exact D1/D2 values select 31.
    for key in rows[0].keys():
        vals = [str(r.get(key, "") or "").strip() for r in rows]
        upper = [v.upper() for v in vals]
        if not ({"D1", "D2"} & set(upper)):
            continue
        chosen = [r for r, v in zip(rows, upper) if v in {"D1", "D2"}]
        diagnostics["candidates"].append({
            "key": key, "method": "fallback_D1_D2", "count": len(chosen),
            "values": sorted(set(vals))[:30],
        })
        if len(chosen) == 31:
            return chosen, {"method": "fallback_D1_D2", "key": key}

    (OUT / "PRIMARY_SELECTION_DIAGNOSTIC.json").write_text(
        json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8"
    )
    raise SystemExit("COULD_NOT_SELECT_EXACTLY_31_PRIMARY_ROWS_FROM_STEP6")

primary_rows, primary_selection = select_primary31(step6_rows)
(OUT / "PRIMARY_SELECTION.json").write_text(
    json.dumps({"count": len(primary_rows), **primary_selection}, indent=2) + "\n",
    encoding="utf-8",
)
print(f"PRIMARY_SELECTION_OK count={len(primary_rows)} method={primary_selection}", flush=True)

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

def fields_for_side(row, side):
    """Return side-specific fields from the Step-6 unblinded pair row."""
    out = {}
    side_words = ["positive", "pos"] if side == "positive" else ["control", "negative", "neg"]
    for k,v in row.items():
        nk = norm(k)
        if any(re.search(rf"(^|_){w}(_|$)", nk) for w in side_words):
            out[k] = v
    return out


def merge_side_fields(pair_row, side):
    return {
        f"step6::{k}": v
        for k, v in fields_for_side(pair_row, side).items()
        if str(v or "").strip()
    }

def find_repo(fields):
    candidates = []
    for k,v in fields.items():
        s = str(v or "").strip()
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", s):
            score = 3 if "repo" in norm(k) or "repository" in norm(k) else 1
            candidates.append((score, s))
        m = re.search(r"github\.com/([^/\s]+)/([^/#\s]+)", s)
        if m:
            candidates.append((4, f"{m.group(1)}/{m.group(2).removesuffix('.git')}"))
    return sorted(candidates, reverse=True)[0][1] if candidates else None


def find_numeric(fields, wanted):
    best = []
    for k,v in fields.items():
        nk = norm(k)
        if wanted not in nk:
            continue
        s = str(v or "").strip()
        m = re.search(r"\b(\d{1,10})\b", s)
        if m:
            score = 4 if nk.endswith(wanted) or nk.endswith(wanted+"_number") or nk.endswith(wanted+"_id") else 2
            best.append((score, int(m.group(1))))
    return sorted(best, reverse=True)[0][1] if best else None


def find_case_id(fields):
    cands = []
    for k,v in fields.items():
        nk = norm(k)
        if "case" not in nk:
            continue
        s = str(v or "").strip()
        m = re.fullmatch(r"\d+", s)
        if m:
            cands.append(int(s))
    return cands[0] if cands else None


def find_text(fields, keywords):
    cands=[]
    for k,v in fields.items():
        nk=norm(k)
        s=str(v or "").strip()
        if not s:
            continue
        if any(w in nk for w in keywords):
            cands.append((len(s), s, k))
    return sorted(cands, reverse=True)[0][1] if cands else ""


def extract_paths(fields):
    paths=[]
    path_re=re.compile(r"(?<![A-Za-z0-9_.-])((?:[A-Za-z0-9_.@()+-]+/)+[A-Za-z0-9_.@()+-]+\.[A-Za-z0-9]{1,8})")
    for k,v in fields.items():
        s=str(v or "")
        for m in path_re.finditer(s):
            p=m.group(1).replace("\\","/")
            if p not in paths:
                paths.append(p)
    return paths


def side_meta(pair_row, side):
    fields=merge_side_fields(pair_row,side)
    meta={
        "repo": find_repo(fields),
        "pr": find_numeric(fields,"pr"),
        "case_id": find_case_id(fields),
        "decision_summary": find_text(fields,["decision_summary","decision","summary","description"]),
        "decision_family": find_text(fields,["family"]),
        "issue_text": find_text(fields,["issue_body","issue_text","issue_title"]),
        "paths_from_metadata": extract_paths(fields),
        "raw_side_fields": fields,
    }
    return meta


def fetch_repo(repo, pr, cache):
    key=safe_name(repo)
    repo_dir=cache/key
    if not (repo_dir/".git").exists():
        if repo_dir.exists(): shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True)
        sh(["git","init","-q"],cwd=repo_dir)
        sh(["git","remote","add","origin",f"https://github.com/{repo}.git"],cwd=repo_dir)
    rc,so,se=sh(["git","fetch","-q","--filter=blob:none","--no-tags","origin",f"+refs/pull/{pr}/head:refs/remotes/origin/pr-{pr}-head"],cwd=repo_dir,timeout=1200)
    if rc!=0:
        raise RuntimeError(f"PR head fetch failed: {se[-2000:]}")
    rc,head,se=sh(["git","rev-parse",f"refs/remotes/origin/pr-{pr}-head"],cwd=repo_dir)
    head=head.strip()
    rc_m,so_m,se_m=sh(["git","fetch","-q","--filter=blob:none","--no-tags","origin",f"+refs/pull/{pr}/merge:refs/remotes/origin/pr-{pr}-merge"],cwd=repo_dir,timeout=1200)
    base=None; source=None
    if rc_m==0:
        rc,merge,se=sh(["git","rev-parse",f"refs/remotes/origin/pr-{pr}-merge"],cwd=repo_dir)
        if rc==0:
            merge=merge.strip()
            rc,parents,se=sh(["git","show","-s","--format=%P",merge],cwd=repo_dir)
            ps=parents.strip().split()
            if len(ps)>=2:
                p1=ps[0]
                sh(["git","fetch","-q","--filter=blob:none","--no-tags","origin",p1],cwd=repo_dir,timeout=1200)
                rc,mb,se=sh(["git","merge-base",p1,head],cwd=repo_dir)
                if rc==0 and mb.strip():
                    base=mb.strip(); source="github_pr_merge_ref"
    if base is None:
        # fallback: first parent of PR head; logged as weaker resolution
        rc,parents,se=sh(["git","show","-s","--format=%P",head],cwd=repo_dir)
        ps=parents.strip().split()
        if ps:
            base=ps[0]; source="pr_head_first_parent_fallback"
    if base is None:
        raise RuntimeError("base resolution failed")
    return repo_dir, base, head, source


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
    text="\n".join(added_lines(diff)) + "\n" + (summary or "")
    identifiers=re.findall(r"\b[A-Za-z_$][A-Za-z0-9_$]{3,}\b",text)
    calls=re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]{2,})\s*\(",text)
    strings=[]
    for m in re.finditer(r"['\"]([^'\"\n]{4,80})['\"]",text):
        val=m.group(1)
        if re.fullmatch(r"[A-Za-z0-9_./:@?&=+ -]+",val):
            strings.append(val)
    cnt=Counter()
    for t in identifiers+calls*2:
        lt=t.lower()
        if lt not in STOP and not lt.isdigit() and len(t)>=4:
            cnt[t]+=1
    ranked=[t for t,_ in cnt.most_common(MAX_QUERY_TERMS*2)]
    # short literal fragments can expose repository idioms such as command -v or github.com
    for s in strings:
        if s not in ranked and len(s)<=50:
            ranked.append(s)
    return ranked[:MAX_QUERY_TERMS]


def line_snippet(content,line_no,radius=20):
    lines=content.splitlines()
    if not lines: return ""
    i=max(0,int(line_no)-1)
    a=max(0,i-radius); b=min(len(lines),i+radius+1)
    return "\n".join(f"{j+1:6d}: {lines[j]}" for j in range(a,b))


def search_prebase(repo_dir, base, targets, terms):
    candidates={}
    target_dirs={str(Path(p).parent) for p in targets}
    target_exts={Path(p).suffix.lower() for p in targets}
    for term in terms:
        rc,out,err=sh(["git","grep","-n","-I","-F","-e",term,base,"--"],cwd=repo_dir,timeout=300)
        if rc not in (0,1):
            continue
        n=0
        for line in out.splitlines():
            if n>=MAX_GREP_HITS_PER_TERM: break
            # format: BASE:path:line:text
            m=re.match(r"^[^:]+:(.*?):(\d+):(.*)$",line)
            if not m: continue
            path=m.group(1); ln=int(m.group(2)); txt=m.group(3)
            if any(seg in path.lower() for seg in ["node_modules/","vendor/","dist/","build/","coverage/",".min."]):
                continue
            key=(path,ln)
            d=candidates.setdefault(key,{"path":path,"line":ln,"line_text":txt,"terms":set(),"score":0.0})
            d["terms"].add(term)
            d["score"] += 1.0
            if str(Path(path).parent) in target_dirs: d["score"] += 1.5
            if Path(path).suffix.lower() in target_exts: d["score"] += 0.4
            if path in targets: d["score"] += 1.0
            n+=1
    rows=[]
    for d in candidates.values():
        d["score"] += 0.7*(len(d["terms"])-1)
        rows.append(d)
    rows.sort(key=lambda x:(x["score"],len(x["terms"])),reverse=True)
    selected=[]
    per_file=Counter()
    for d in rows:
        if len(selected)>=MAX_CANDIDATES: break
        if per_file[d["path"]]>=4: continue
        content=git_show(repo_dir,base,d["path"])
        if content is None or len(content.encode("utf-8",errors="ignore"))>MAX_FILE_BYTES:
            continue
        selected.append({
            "path":d["path"],"line":d["line"],"score":round(d["score"],3),
            "matched_terms":sorted(d["terms"]),"snippet":line_snippet(content,d["line"]),
        })
        per_file[d["path"]]+=1
    return selected


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
rng=random.Random(SEED)
sealed_rows=[]
index_rows=[]
errors=[]
status_counts=Counter()

# Deterministic order by pair ID, then randomize side labels with frozen seed.
primary_rows_sorted=sorted(primary_rows,key=lambda r: pair_id_of(r) or "")

for idx,row in enumerate(primary_rows_sorted,1):
    pid=pair_id_of(row) or f"PAIR-{idx:03d}"
    print(f"PAIR_START {idx}/31 {pid}", flush=True)
    pmeta=side_meta(row,"positive")
    nmeta=side_meta(row,"control")

    labels=["A","B"]
    rng.shuffle(labels)
    mapping={"positive":labels[0],"control":labels[1]}
    sealed_rows.append({"pair_id":pid,"side_A_role":"positive" if mapping["positive"]=="A" else "control",
                        "side_B_role":"positive" if mapping["positive"]=="B" else "control"})

    pair_dir=OUT/"blinded_packets"/pid
    pair_dir.mkdir(parents=True,exist_ok=True)

    for role,meta in [("positive",pmeta),("control",nmeta)]:
        blind_side=mapping[role]

        # Resume support: keep any side already extracted successfully by the timed-out v1 job.
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
            if not meta.get("repo") or not meta.get("pr"):
                raise RuntimeError(f"metadata incomplete: repo={meta.get('repo')} pr={meta.get('pr')}")
            repo_dir,base,head,bsource=fetch_repo(meta["repo"],int(meta["pr"]),cache)
            ch=changed_files(repo_dir,base,head)
            targets=choose_targets(meta,ch)
            hist=diff_for(repo_dir,base,head,targets) if targets else ""
            terms=query_terms(hist,meta.get("decision_summary",""))
            bctx={}
            for p in targets:
                content=git_show(repo_dir,base,p)
                if content is not None:
                    if len(content.encode("utf-8",errors="ignore"))<=MAX_FILE_BYTES:
                        bctx[p]=content
                    else:
                        bctx[p]=content[:MAX_FILE_BYTES//2] + "\n\n[TRUNCATED]\n"
            cands=search_prebase(repo_dir,base,targets,terms)
            resolved={
                "status":"PASS","note":"","base_sha":base,"head_sha":head,"base_resolution_source":bsource,
                "target_files":targets,"historical_diff":hist,"query_terms":terms,"base_context":bctx,"candidates":cands,
            }
        except Exception as e:
            resolved={"status":"FAIL","note":str(e)[:3000],"base_context":{},"candidates":[]}
            errors.append({"pair_id":pid,"role":role,"error":str(e)[:3000],"meta":meta})
        status_counts[resolved["status"]]+=1
        write_side_packet(pair_dir,blind_side,meta,resolved,row)
        print(f"SIDE_DONE {pid} {blind_side} status={resolved['status']} repo={meta.get('repo')} pr={meta.get('pr')} candidates={len(resolved.get('candidates',[]))}", flush=True)
        index_rows.append({
            "pair_id":pid,"blind_side":blind_side,"repository":meta.get("repo") or "","pr_number":meta.get("pr") or "",
            "case_id":meta.get("case_id") or "","decision_family":meta.get("decision_family") or "",
            "decision_summary":meta.get("decision_summary") or "","extraction_status":resolved.get("status"),
            "target_file_count":len(resolved.get("target_files",[])),"candidate_count":len(resolved.get("candidates",[])),
            "base_resolution_source":resolved.get("base_resolution_source","")
        })

# sealed key is deliberately outside blinded packet tree
with SEALED.open("w",newline="",encoding="utf-8") as f:
    w=csv.DictWriter(f,fieldnames=["pair_id","side_A_role","side_B_role"])
    w.writeheader(); w.writerows(sealed_rows)

with (OUT/"BLINDED_PACKET_INDEX.csv").open("w",newline="",encoding="utf-8") as f:
    fields=["pair_id","blind_side","repository","pr_number","case_id","decision_family","decision_summary","extraction_status","target_file_count","candidate_count","base_resolution_source"]
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(index_rows)

(OUT/"EXTRACTION_ERRORS.json").write_text(json.dumps(errors,indent=2)+"\n",encoding="utf-8")

protocol = {
    "schema":"T1_PRIMARY31_CONTEXT_CENSUS_v4",
    "population":"all 31 pre-existing primary D1/D2 decision-level matches; no outcome-based subsampling",
    "purpose":"collect symmetric chronology-safe pre-change repository context for both matched decisions",
    "blinding":"positive/control roles randomized to A/B using frozen seed; scanner labels omitted from blinded packets",
    "seed":SEED,
    "retrieval":"same deterministic procedure on both sides: historical decision context identifies target files/query terms; all candidate precedent snippets are read from the resolved pre-PR base only",
    "candidate_search":"git grep fixed-string query terms on pre-PR base; capped and ranked deterministically; no LLM selection in extraction",
    "important_limit":"retrieval candidates are evidence packets, not labels. Presence of a search hit does not itself establish risky precedent or a safer alternative.",
    "next_annotation_fields":[
        "target_mechanism_precedent_present","precedent_strength","safer_local_alternative_present",
        "alternative_strength","decision_required_for_task","context_completeness","rationale_with_candidate_ids"
    ],
}
(OUT/"FROZEN_PROTOCOL.json").write_text(json.dumps(protocol,indent=2)+"\n",encoding="utf-8")

qc={
    "schema":"T1_PRIMARY31_CONTEXT_CENSUS_v4",
    "primary_rows_loaded":len(primary_rows),
    "unique_pair_ids":len({pair_id_of(r) for r in primary_rows if pair_id_of(r)}),
    "blinded_sides":len(index_rows),
    "status_counts":dict(status_counts),
    "sealed_key_sha256":sha256(SEALED),
    "source_files":{k:(str(v) if v else None) for k,v in sources.items()},
    "source_sha256":{k:(sha256(v) if v and v.exists() else None) for k,v in sources.items()},
    "pass_condition":"31 primary rows and 62 blinded sides; extraction failures are retained and never silently dropped",
}
(OUT/"QC.json").write_text(json.dumps(qc,indent=2)+"\n",encoding="utf-8")

checks=[]
for p in sorted((OUT/"blinded_packets").rglob("*")):
    if p.is_file(): checks.append(f"{sha256(p)}  {p.relative_to(OUT)}")
for p in [OUT/"BLINDED_PACKET_INDEX.csv",OUT/"FROZEN_PROTOCOL.json",OUT/"QC.json",OUT/"SOURCE_HEADERS.json",OUT/"SOURCE_LOCATIONS.json"]:
    if p.exists(): checks.append(f"{sha256(p)}  {p.relative_to(OUT)}")
(OUT/"SHA256SUMS.txt").write_text("\n".join(checks)+"\n",encoding="utf-8")

print(json.dumps(qc,indent=2))
print("STATUS=DONE")
PY

cd "$ROOT"
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
  QC.json \
  SOURCE_HEADERS.json \
  SOURCE_LOCATIONS.json \
  FROZEN_PROTOCOL.json

echo
echo "=== OUTPUTS ==="
ls -lh "$BLIND" "$SEALED" "$QCARCH"
sha256sum "$BLIND" "$SEALED" "$QCARCH"
echo "STATUS=ARCHIVED"
