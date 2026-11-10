#!/usr/bin/env python3
import csv, json, os, re, sys, zipfile
from pathlib import Path

RUN_RE = re.compile(r'\bC(0(?:0[1-9]|1[0-6]))\b', re.I)
PAIR_RE = re.compile(r'\bS5PAIR-(001|016|025|044)\b', re.I)
REPO_RE = re.compile(r'\brepo_[0-9a-f]{8,}\.tar\.gz\b', re.I)
POS_RE = re.compile(r'\b(P0|positive|pos)\b', re.I)
NEG_RE = re.compile(r'\b(N0|negative|neg)\b', re.I)
PAIR_ORDER = ["S5PAIR-001", "S5PAIR-016", "S5PAIR-025", "S5PAIR-044"]
RUNS = [f"C{i:03d}" for i in range(1,17)]

CAL = Path(os.environ.get("CAL", Path.home()/"research_artifacts/counterfactual_replay_r1/calibration_medium")).expanduser()
ROOT = CAL.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else CAL/"corrected_target_eval_v1"
OUT.mkdir(parents=True, exist_ok=True)

hist = CAL/"historical_validation/bundle/HISTORICAL_VALIDATION_MANIFEST.csv"
if not hist.exists():
    print(f"ERROR missing historical manifest: {hist}")
    sys.exit(2)

hist_rows = {}
with hist.open(newline='', encoding='utf-8') as f:
    rows = list(csv.reader(f))
for row in rows:
    if not row or not row[0].startswith("S5PAIR-"):
        continue
    if row[0] in PAIR_ORDER:
        hist_rows[row[0]] = row

if set(hist_rows) != set(PAIR_ORDER):
    print("ERROR historical manifest does not contain all four calibration pairs")
    print("FOUND", sorted(hist_rows))
    sys.exit(2)

def norm_cond(s):
    s = (s or "").strip().lower()
    if s in {"p0","positive","pos","p"}: return "P0"
    if s in {"n0","negative","neg","n"}: return "N0"
    if POS_RE.search(s): return "P0"
    if NEG_RE.search(s): return "N0"
    return None

def depth_from(base, p):
    try: return len(p.relative_to(base).parts)
    except Exception: return 99

# Discover small mapping/index files only. Avoid repos/snapshots/work/dbs.
records = []
prune = {"repos","snapshots","work","dbs","codeql_dbs","node_modules",".git"}
for base in [CAL]:
    for root, dirs, files in os.walk(base):
        rp = Path(root)
        if depth_from(base, rp) > 5:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in prune]
        for fn in files:
            p = rp/fn
            if p.suffix.lower() not in {".csv",".tsv",".json",".jsonl",".txt",".md"}:
                continue
            low = fn.lower()
            if not any(k in low for k in ["manifest","mapping","map","index","calib","run","task","meta"]):
                continue
            try:
                if p.stat().st_size > 5_000_000:
                    continue
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for line in text.splitlines():
                rm = RUN_RE.search(line); pm = PAIR_RE.search(line)
                if not rm or not pm: continue
                run = "C" + rm.group(1)
                pair = "S5PAIR-" + pm.group(1)
                cond = norm_cond(line)
                repo_m = REPO_RE.search(line)
                records.append((run,pair,cond,repo_m.group(0) if repo_m else None,str(p),line[:500]))

# CSV-aware pass catches columns split across a row.
for root, dirs, files in os.walk(CAL):
    rp = Path(root)
    if depth_from(CAL, rp) > 5:
        dirs[:] = []
        continue
    dirs[:] = [d for d in dirs if d not in prune]
    for fn in files:
        p = rp/fn
        if p.suffix.lower() not in {".csv",".tsv"}: continue
        try:
            if p.stat().st_size > 5_000_000: continue
            delim = '\t' if p.suffix.lower()=='.tsv' else ','
            with p.open(newline='', encoding='utf-8', errors='replace') as f:
                for row in csv.reader(f, delimiter=delim):
                    joined = " | ".join(row)
                    rm=RUN_RE.search(joined); pm=PAIR_RE.search(joined)
                    if not rm or not pm: continue
                    run="C"+rm.group(1); pair="S5PAIR-"+pm.group(1)
                    cond=None
                    for cell in row:
                        c=norm_cond(cell)
                        if c: cond=c; break
                    repo_m=REPO_RE.search(joined)
                    records.append((run,pair,cond,repo_m.group(0) if repo_m else None,str(p),joined[:500]))
        except Exception:
            pass

# Deduplicate mapping evidence and require unique pair+condition for every run.
run_map = {}
ambig = []
for run in RUNS:
    rs = [r for r in records if r[0] == run]
    pairs = sorted({r[1] for r in rs if r[1]})
    conds = sorted({r[2] for r in rs if r[2]})
    repos = sorted({r[3] for r in rs if r[3]})
    if len(pairs)==1 and len(conds)==1:
        run_map[run] = {"pair":pairs[0],"condition":conds[0],"repo_archive":repos[0] if len(repos)==1 else None,
                        "mapping_sources":";".join(sorted({r[4] for r in rs}))}
    else:
        ambig.append((run,pairs,conds,repos,sorted({r[4] for r in rs})))

# Find per-run input ZIPs / extracted input dirs.
def bounded_files(base, maxdepth=6):
    if not base.exists(): return
    for root, dirs, files in os.walk(base):
        rp=Path(root)
        if depth_from(base,rp)>maxdepth:
            dirs[:]=[]; continue
        dirs[:] = [d for d in dirs if d not in {"work","codeql_dbs","node_modules",".git"}]
        for fn in files: yield rp/fn

all_files = list(bounded_files(CAL,6)) + list(bounded_files(ROOT,3))

input_ref = {}
patch_ref = {}
for run in RUNS:
    inz = [p for p in all_files if p.name.upper() == f"{run}_INPUT.ZIP"]
    if inz: input_ref[run] = ("input_zip", str(sorted(inz,key=lambda p:len(str(p)))[0]))
    outs = [p for p in all_files if p.name.upper() == f"{run}_OUTPUT.ZIP"]
    if outs: patch_ref[run] = ("output_zip", str(sorted(outs,key=lambda p:len(str(p)))[0]))

# Extracted submission.patch under a C### path is also accepted.
for p in all_files:
    if p.name != "submission.patch": continue
    m = RUN_RE.search(str(p).upper())
    if m:
        run="C"+m.group(1)
        patch_ref.setdefault(run,("patch",str(p)))

# Giant input ZIP fallback: member can be C###_INPUT.zip or C###/.../repo.tar.gz.
giant_candidates = [p for p in all_files if p.name == "CALIBRATION_16_INPUTS.zip"]
if giant_candidates:
    giant = giant_candidates[0]
    try:
        with zipfile.ZipFile(giant) as z:
            names = z.namelist()
        for run in RUNS:
            if run in input_ref: continue
            nested=[n for n in names if Path(n).name.upper()==f"{run}_INPUT.ZIP"]
            repo=[n for n in names if run in n.upper() and Path(n).name=="repo.tar.gz"]
            if nested: input_ref[run] = ("nested_input_zip", f"{giant}::{nested[0]}")
            elif repo: input_ref[run] = ("giant_repo_member", f"{giant}::{repo[0]}")
    except Exception:
        pass

# Dedup repo archive fallback.
repo_dirs = [CAL/"dedup/repos", CAL/"repos", CAL/"snapshots"]
for run,m in run_map.items():
    if run in input_ref: continue
    ra=m.get("repo_archive")
    if ra:
        for d in repo_dirs:
            p=d/ra
            if p.exists():
                input_ref[run]=("repo_tar",str(p)); break

# Last bounded lookup by repo archive name if mapping has it.
for run,m in run_map.items():
    if run in input_ref: continue
    ra=m.get("repo_archive")
    if ra:
        hits=[p for p in all_files if p.name==ra]
        if hits: input_ref[run]=("repo_tar",str(hits[0]))

missing_map=[r for r in RUNS if r not in run_map]
missing_input=[r for r in RUNS if r not in input_ref]
missing_patch=[r for r in RUNS if r not in patch_ref]

print("=== CORRECTED TARGET EVAL PREFLIGHT ===")
print("CAL=", CAL)
print("mapping_records=", len(records))
for run in RUNS:
    m=run_map.get(run,{})
    print(run, m.get('pair','?'), m.get('condition','?'), "BASE="+input_ref.get(run,("?","?"))[0], "PATCH="+patch_ref.get(run,("?","?"))[0])

if missing_map or missing_input or missing_patch:
    print("\nPREFLIGHT_STATUS=FAIL")
    if missing_map:
        print("MISSING_OR_AMBIGUOUS_MAPPING=", ",".join(missing_map))
        for item in ambig:
            if item[0] in missing_map: print("MAP_EVIDENCE", item)
    if missing_input: print("MISSING_BASE_INPUT=", ",".join(missing_input))
    if missing_patch: print("MISSING_OUTPUT_PATCH=", ",".join(missing_patch))
    print("No CodeQL jobs were submitted.")
    sys.exit(3)

# Validate exactly 2 P0 + 2 N0 per pair.
for pair in PAIR_ORDER:
    vals=[run_map[r]['condition'] for r in RUNS if run_map[r]['pair']==pair]
    if sorted(vals) != ["N0","N0","P0","P0"]:
        print(f"PREFLIGHT_STATUS=FAIL pair balance {pair}: {vals}")
        sys.exit(3)

out_csv=OUT/"RUN_MANIFEST.csv"
with out_csv.open('w',newline='',encoding='utf-8') as f:
    w=csv.writer(f)
    w.writerow(["run_id","pair_id","condition","target_rule","base_kind","base_ref","patch_kind","patch_ref","mapping_sources"])
    for run in RUNS:
        m=run_map[run]; pair=m['pair']; h=hist_rows[pair]
        # Historical manifest columns: pair, repo, url, base_sha, head_sha, repo_archive, target_rule, ...
        target=h[6]
        bk,br=input_ref[run]; pk,pr=patch_ref[run]
        w.writerow([run,pair,m['condition'],target,bk,br,pk,pr,m['mapping_sources']])

print("PREFLIGHT_STATUS=PASS")
print("RUN_MANIFEST=", out_csv)
