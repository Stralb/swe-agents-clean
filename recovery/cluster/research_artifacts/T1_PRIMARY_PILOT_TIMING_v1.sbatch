#!/bin/bash
#SBATCH --job-name=t1timing
#SBATCH --partition=bigbatch
#SBATCH --time=01:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T1_PRIMARY_PILOT_TIMING_v1.out

set -euo pipefail

ROOT="$HOME/research_artifacts"
GENROOT="$ROOT/T1_PRIMARY_PILOT_GENERATIONS_v1_EXTRACTED/T1_PRIMARY_PILOT_GENERATIONS_v1"
AUDIT="$ROOT/T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
OUT="$ROOT/T1_PRIMARY_PILOT_TIMING_v1"
NODE22="$HOME/tools/node22/bin"
TMP="${SLURM_TMPDIR:-/tmp}/t1timing_${SLURM_JOB_ID}"

mkdir -p "$OUT" "$TMP"
export PATH="$NODE22:$PATH"

python3 -u <<'PY'
import csv
import json
import os
import random
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
GENROOT = ROOT / "T1_PRIMARY_PILOT_GENERATIONS_v1_EXTRACTED/T1_PRIMARY_PILOT_GENERATIONS_v1"
AUDIT = ROOT / "T1_PRIMARY_PILOT_PACKET_AUDIT_v1.tar.gz"
OUT = ROOT / "T1_PRIMARY_PILOT_TIMING_v1"
TMP = Path(os.environ.get("SLURM_TMPDIR") or f"/tmp/t1timing_{os.environ['SLURM_JOB_ID']}")
OUT.mkdir(parents=True, exist_ok=True)

VARIANTS = ["BASELINE", "RUN_001", "RUN_002", "RUN_006", "RUN_008"]
REPS = 5
SEED = 20260921
NAME_PATTERN = r"queries complete under 5ms for 50\+50 rows|context-store: sub-5ms query timing"

def run(cmd, cwd=None, timeout=1800):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, timeout=timeout)

def must(cmd, cwd=None, timeout=1800):
    p = run(cmd, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"command failed {cmd}\n{p.stderr[-3000:]}")
    return p

def safe_rel(raw):
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts:
        raise RuntimeError("unsafe path")
    return p

with tarfile.open(AUDIT, "r:gz") as tf:
    m = next(x for x in tf.getmembers() if x.isfile() and x.name.endswith("/SEALED_PROVENANCE.json"))
    prov = json.loads(tf.extractfile(m).read().decode())["PAIR_PRIMARY"]

repo_url = f"https://github.com/{prov['repository']}.git"
base_sha = prov["true_base_sha"]

repo = TMP / "repo"
must(["git","clone","-q","--filter=blob:none","--no-checkout",repo_url,str(repo)], timeout=900)
must(["git","fetch","-q","origin",base_sha], cwd=repo, timeout=900)

worktrees = {}
for variant in VARIANTS:
    wt = TMP / variant
    must(["git","worktree","add","-q","--detach",str(wt),base_sha], cwd=repo)
    worktrees[variant] = wt

    if variant != "BASELINE":
        data = json.loads((GENROOT / f"{variant}_generation.json").read_text())
        for item in data["files"]:
            rel = safe_rel(item["path"])
            dst = wt / rel
            resolved = dst.resolve(strict=False)
            root = wt.resolve()
            if resolved != root and root not in resolved.parents:
                raise RuntimeError("path escape")
            op = item.get("op","write")
            if op == "write":
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(item["content"], encoding="utf-8")
            elif op == "delete":
                if dst.exists():
                    dst.unlink()
            else:
                raise RuntimeError("unsupported op")

# Install dependencies once in baseline, then reuse the identical dependency tree.
base = worktrees["BASELINE"]
must(["npm","ci"], cwd=base, timeout=1800)
for variant in VARIANTS[1:]:
    target = worktrees[variant] / "node_modules"
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    target.symlink_to(base / "node_modules", target_is_directory=True)

# Locate the exact source test files by the frozen test names.
needle1 = "queries complete under 5ms for 50+50 rows"
needle2 = "context-store: sub-5ms query timing"
hits = []
for p in base.rglob("*"):
    if not p.is_file():
        continue
    if "node_modules" in p.parts or ".git" in p.parts:
        continue
    if p.suffix not in {".ts",".js",".mjs"}:
        continue
    try:
        txt = p.read_text(errors="ignore")
    except Exception:
        continue
    if needle1 in txt or needle2 in txt:
        hits.append(p.relative_to(base))

if not hits:
    raise RuntimeError("could not locate timing-test source files")

# Compile test trees once per variant.
compiled_files = {}
for variant, wt in worktrees.items():
    must(["node","scripts/compile-tests.mjs"], cwd=wt, timeout=900)
    current = []
    for rel in sorted(set(hits)):
        # compile-tests preserves relative path under dist-test and changes .ts -> .js
        dest = Path("dist-test") / rel
        if dest.suffix == ".ts":
            dest = dest.with_suffix(".js")
        if (wt / dest).exists():
            current.append(dest.as_posix())
    if not current:
        raise RuntimeError(f"no compiled timing-test files for {variant}")
    compiled_files[variant] = current

# Fixed randomized round-robin schedule: same node, sequential execution.
rng = random.Random(SEED)
schedule = []
for rep in range(1, REPS + 1):
    order = VARIANTS.copy()
    rng.shuffle(order)
    for within_rep, variant in enumerate(order, 1):
        schedule.append((rep, within_rep, variant))

with (OUT/"FROZEN_TIMING_SCHEDULE.csv").open("w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["rep","within_rep_order","variant"])
    w.writerows(schedule)

rows = []
for overall, (rep, within_rep, variant) in enumerate(schedule, 1):
    wt = worktrees[variant]
    cmd = [
        "node",
        "--import", "./scripts/dist-test-resolve.mjs",
        "--experimental-test-isolation=process",
        "--test-reporter=./scripts/test-reporter-compact.mjs",
        "--test",
        "--test-name-pattern", NAME_PATTERN,
        *compiled_files[variant],
    ]
    p = run(cmd, cwd=wt, timeout=600)
    text = (p.stdout or "") + "\n" + (p.stderr or "")
    # Count only the two named timing assertions if reporter exposes them.
    named_fail = sum(
        1 for name in (needle1, needle2)
        if re.search(r"(?:✖|not ok).*" + re.escape(name), text, re.I)
    )
    row = {
        "overall_order": overall,
        "rep": rep,
        "within_rep_order": within_rep,
        "variant": variant,
        "returncode": p.returncode,
        "named_failure_count": named_fail,
        "targeted_pass": p.returncode == 0,
    }
    rows.append(row)

    log = OUT / f"{variant}_rep{rep}.log"
    log.write_text(text, encoding="utf-8")
    print(
        variant,
        f"rep={rep}",
        f"rc={p.returncode}",
        f"pass={int(p.returncode==0)}",
        flush=True,
    )

with (OUT/"TIMING_RESULTS.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

summary = {}
for variant in VARIANTS:
    vr = [r for r in rows if r["variant"] == variant]
    summary[variant] = {
        "passes": sum(r["targeted_pass"] for r in vr),
        "runs": len(vr),
        "failures": sum(not r["targeted_pass"] for r in vr),
    }
(OUT/"TIMING_SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")

print("SUMMARY")
for v in VARIANTS:
    s = summary[v]
    print(v, f"{s['passes']}/{s['runs']} PASS")
print("STATUS=DONE")
PY
