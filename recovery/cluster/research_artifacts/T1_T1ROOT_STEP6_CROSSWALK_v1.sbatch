#!/bin/bash
#SBATCH --job-name=t1cross
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_T1ROOT_STEP6_CROSSWALK_%j.out

set -euo pipefail

GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
import csv, io, json, os, re, tarfile, zipfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
GROUP = int(os.environ["GROUP"])

ROOTS = {
    "R1": "CROOT-00668-01",
    "R2": "CROOT-16534-01",
    "R3": "CROOT-04131-01",
    "R4": "CROOT-10819-01",
    "R5": "CROOT-10339-01",
    "R6": "CROOT-16213-01",
}
GROUP_ROOTS = {
    0: ["R1","R2","R3"],
    1: ["R4","R5","R6"],
}[GROUP]

STEP6 = ROOT / "DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz"
REPL = ROOT / "T1_REPLACEMENT3_EXTRACT_v1.tar.gz"
SEL6 = ROOT / "T1_SELECTED6_EXTRACT_v1.tar.gz"

if not STEP6.exists():
    raise SystemExit(f"MISSING_STEP6={STEP6}")

def interesting_row(row):
    s = json.dumps(row, ensure_ascii=False)
    return s

def reduce_fields(obj):
    if not isinstance(obj, dict):
        return obj
    keep = {}
    for k,v in obj.items():
        lk = str(k).lower()
        if any(t in lk for t in (
            "pair","root","positive","control","negative","case",
            "workflow","match","tier","quality","decision","repo","side"
        )):
            keep[k] = v
    return keep or obj

# Extract T1 metadata for separability.
meta = {}
for arch in (REPL, SEL6):
    if not arch.exists():
        continue
    with tarfile.open(arch, "r:*") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith("/METADATA.json"):
                continue
            for alias in GROUP_ROOTS:
                rid = ROOTS[alias]
                if rid not in m.name:
                    continue
                data = json.loads(tf.extractfile(m).read().decode("utf-8", errors="ignore"))
                targets = set(data.get("target_files") or [])
                precedents = set(data.get("saved_precedent_files") or [])
                non_target = sorted(precedents - targets)
                meta[alias] = {
                    "root_id": rid,
                    "target_count": len(targets),
                    "precedent_count": len(precedents),
                    "non_target_precedent_count": len(non_target),
                    "separable_candidate": bool(non_target),
                    "focal_mechanism": data.get("focal_mechanism"),
                }

# Search every structured/text member in Step6 for exact root IDs.
hits = {a: [] for a in GROUP_ROOTS}

with tarfile.open(STEP6, "r:*") as tf:
    for m in tf.getmembers():
        if not m.isfile() or m.size > 50*1024*1024:
            continue
        name = m.name.lower()
        if not name.endswith((".csv",".tsv",".json",".jsonl",".txt",".md")):
            continue
        try:
            raw = tf.extractfile(m).read()
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            continue

        relevant = [a for a in GROUP_ROOTS if ROOTS[a] in text]
        if not relevant:
            continue

        if name.endswith((".csv",".tsv")):
            try:
                dialect = csv.excel_tab if name.endswith(".tsv") else csv.excel
                rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
                for row in rows:
                    rs = interesting_row(row)
                    for a in relevant:
                        if ROOTS[a] in rs:
                            hits[a].append({
                                "member": m.name,
                                "type": "row",
                                "record": reduce_fields(row),
                            })
            except Exception:
                pass

        elif name.endswith(".jsonl"):
            for line in text.splitlines():
                if not line.strip():
                    continue
                for a in relevant:
                    if ROOTS[a] not in line:
                        continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        obj = {"raw": line[:4000]}
                    hits[a].append({
                        "member": m.name,
                        "type": "jsonl",
                        "record": reduce_fields(obj),
                    })

        elif name.endswith(".json"):
            try:
                obj = json.loads(text)
            except Exception:
                obj = None
            for a in relevant:
                rid = ROOTS[a]
                if obj is not None:
                    # Recursively capture small dicts containing the root.
                    stack = [obj]
                    captured = 0
                    while stack and captured < 30:
                        x = stack.pop()
                        if isinstance(x, dict):
                            sx = json.dumps(x, ensure_ascii=False)
                            if rid in sx and len(sx) < 50000:
                                hits[a].append({
                                    "member": m.name,
                                    "type": "json",
                                    "record": reduce_fields(x),
                                })
                                captured += 1
                            stack.extend(x.values())
                        elif isinstance(x, list):
                            stack.extend(x)
                else:
                    idx = text.find(rid)
                    hits[a].append({
                        "member": m.name,
                        "type": "snippet",
                        "record": {"snippet": text[max(0,idx-1500):idx+4000]},
                    })
        else:
            for a in relevant:
                rid = ROOTS[a]
                idx = text.find(rid)
                hits[a].append({
                    "member": m.name,
                    "type": "snippet",
                    "record": {"snippet": text[max(0,idx-1500):idx+4000]},
                })

# Derive concise pair IDs/match tiers where possible.
summary = {}
for a in GROUP_ROOTS:
    pair_ids = set()
    tiers = set()
    controls = set()
    for h in hits[a]:
        s = json.dumps(h["record"], ensure_ascii=False)
        pair_ids.update(re.findall(r"S5PAIR-\d+", s))
        for pat in (r'"(?:match_quality|quality|tier)"\s*:\s*"([^"]+)"',
                    r'\b(D[1-4])\b'):
            for x in re.findall(pat, s, re.I):
                if isinstance(x, tuple):
                    x = next((y for y in x if y), "")
                if x:
                    tiers.add(str(x))
        # anonymized control identifiers if fields expose them
        if isinstance(h["record"], dict):
            for k,v in h["record"].items():
                lk = str(k).lower()
                if ("control" in lk or "negative" in lk) and v not in (None,""):
                    controls.add(str(v)[:300])

    summary[a] = {
        **meta.get(a, {"root_id": ROOTS[a]}),
        "step6_hit_count": len(hits[a]),
        "pair_ids": sorted(pair_ids),
        "match_tiers": sorted(tiers),
        "control_refs": sorted(controls)[:20],
    }

out = ROOT / f"T1_T1ROOT_STEP6_CROSSWALK_G{GROUP}.json"
out.write_text(json.dumps({
    "group": GROUP,
    "summary": summary,
    "raw_hits": hits,
}, indent=2, ensure_ascii=False) + "\n")

print("STATUS=DONE")
print("GROUP=", GROUP)
for a in GROUP_ROOTS:
    s = summary[a]
    print(
        a,
        "MATCH_HITS=", s.get("step6_hit_count",0),
        "PAIR_IDS=", ",".join(s.get("pair_ids",[])) or "NONE",
        "TIERS=", ",".join(s.get("match_tiers",[])) or "NONE",
        "SEPARABLE_X=", s.get("separable_candidate","UNKNOWN"),
        "NON_TARGET_X_FILES=", s.get("non_target_precedent_count","UNKNOWN"),
    )
print("OUTPUT=", out)
PY
