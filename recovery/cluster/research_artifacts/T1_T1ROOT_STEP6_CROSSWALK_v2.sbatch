#!/bin/bash
#SBATCH --job-name=t1cross2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_T1ROOT_STEP6_CROSSWALK_v2_%j.out

set -euo pipefail
GROUP="${GROUP:?submit with --export=ALL,GROUP=0 or GROUP=1}"

python3 -u <<'PY'
import csv, io, json, os, re, tarfile
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
GROUP_ROOTS = {0:["R1","R2","R3"], 1:["R4","R5","R6"]}[GROUP]

STEP6 = ROOT / "DECISION_LEVEL_CONTROLS_STEP6_v1.0.tar.gz"
T1_ARCHIVES = [
    ROOT / "T1_REPLACEMENT3_EXTRACT_v1.tar.gz",
    ROOT / "T1_SELECTED6_EXTRACT_v1.tar.gz",
]

if not STEP6.exists():
    raise SystemExit("missing Step6 archive")

def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k,v in obj.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(v,p))
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            out.update(flatten(v,f"{prefix}[{i}]"))
    else:
        out[prefix] = obj
    return out

def first_matching(flat, needles):
    for k,v in flat.items():
        lk = k.lower()
        if any(n in lk for n in needles) and v not in (None,""):
            return v
    return None

# Recover bridging identifiers from the frozen T1 metadata.
bridge = {}
for arch in T1_ARCHIVES:
    if not arch.exists():
        continue
    with tarfile.open(arch, "r:*") as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith("/METADATA.json"):
                continue
            alias = next((a for a in GROUP_ROOTS if ROOTS[a] in m.name), None)
            if not alias:
                continue
            obj = json.loads(tf.extractfile(m).read().decode("utf-8", errors="ignore"))
            flat = flatten(obj)
            case_id = first_matching(flat, ["case_id","case.id","positive_case"])
            workflow_id = first_matching(flat, ["workflow_id","workflow.id"])
            repo_id = first_matching(flat, ["repo_id","repository_id"])
            family = first_matching(flat, ["decision_family","functional_family","family"])
            summary = first_matching(flat, ["focal_mechanism","decision_summary","mechanism_summary"])
            target_files = first_matching(flat, ["target_files"]) or []
            precedent_files = first_matching(flat, ["saved_precedent_files","precedent_files"]) or []
            bridge[alias] = {
                "root_id": ROOTS[alias],
                "case_id": case_id,
                "workflow_id": workflow_id,
                "repo_id": repo_id,
                "family": family,
                "summary": summary,
                "target_files": target_files,
                "precedent_files": precedent_files,
            }

# Parse all structured rows in Step6 and match by case/workflow id.
rows = []
with tarfile.open(STEP6, "r:*") as tf:
    for m in tf.getmembers():
        if not m.isfile() or m.size > 100*1024*1024:
            continue
        low = m.name.lower()
        if not low.endswith((".csv",".tsv",".jsonl",".json")):
            continue
        try:
            text = tf.extractfile(m).read().decode("utf-8", errors="ignore")
        except Exception:
            continue

        if low.endswith((".csv",".tsv")):
            try:
                dialect = csv.excel_tab if low.endswith(".tsv") else csv.excel
                for r in csv.DictReader(io.StringIO(text), dialect=dialect):
                    rows.append((m.name, r))
            except Exception:
                pass
        elif low.endswith(".jsonl"):
            for line in text.splitlines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append((m.name, obj))
                except Exception:
                    pass
        else:
            try:
                obj = json.loads(text)
            except Exception:
                continue
            stack = [obj]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    rows.append((m.name, x))
                    stack.extend(x.values())
                elif isinstance(x, list):
                    stack.extend(x)

def row_text(r):
    try:
        return json.dumps(r, ensure_ascii=False, sort_keys=True)
    except Exception:
        return str(r)

result = {}
raw = {}
for alias in GROUP_ROOTS:
    b = bridge.get(alias, {})
    ids = []
    for key in ("case_id","workflow_id"):
        v = b.get(key)
        if v not in (None,""):
            ids.append(str(v))

    matches = []
    for member, r in rows:
        s = row_text(r)
        if not ids or not any(re.search(rf'(?<!\d){re.escape(i)}(?!\d)', s) for i in ids):
            continue
        matches.append((member,r))

    pair_ids = set()
    tiers = set()
    side_refs = set()
    for member,r in matches:
        s = row_text(r)
        pair_ids.update(re.findall(r"S5PAIR-\d+", s))
        tiers.update(re.findall(r"\bD[1-4]\b", s))
        for k,v in r.items():
            lk = str(k).lower()
            if any(x in lk for x in ("pair_id","match_tier","tier","control","negative","side")) and v not in (None,""):
                side_refs.add(f"{k}={v}")

    targets = set(b.get("target_files") or []) if isinstance(b.get("target_files"), list) else set()
    precedents = set(b.get("precedent_files") or []) if isinstance(b.get("precedent_files"), list) else set()
    non_target = sorted(precedents - targets)

    result[alias] = {
        "root_id": b.get("root_id"),
        "bridge_found": bool(ids),
        "step6_match_count": len(matches),
        "pair_ids": sorted(pair_ids),
        "tiers": sorted(tiers),
        "separable_x": bool(non_target),
        "non_target_x_count": len(non_target),
    }
    raw[alias] = {
        "bridge": b,
        "matches": [{"member":m,"record":r} for m,r in matches[:50]],
    }

public = ROOT / f"T1_T1ROOT_STEP6_CROSSWALK_v2_G{GROUP}_PUBLIC.json"
sealed = ROOT / f"T1_T1ROOT_STEP6_CROSSWALK_v2_G{GROUP}_SEALED.json"
public.write_text(json.dumps(result, indent=2)+"\n")
sealed.write_text(json.dumps(raw, indent=2, ensure_ascii=False)+"\n")

print("STATUS=DONE")
print("GROUP=", GROUP)
for alias in GROUP_ROOTS:
    r = result[alias]
    print(
        alias,
        "BRIDGE=", int(r["bridge_found"]),
        "MATCHES=", r["step6_match_count"],
        "PAIR_IDS=", ",".join(r["pair_ids"]) or "NONE",
        "TIERS=", ",".join(r["tiers"]) or "NONE",
        "SEPARABLE_X=", r["separable_x"],
        "NON_TARGET_X=", r["non_target_x_count"],
    )
print("PUBLIC=", public)
print("SEALED=", sealed)
PY
