#!/bin/bash
#SBATCH --job-name=t2codeql
#SBATCH --partition=batch
#SBATCH --time=01:30:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_CODEQL_BLIND_v1_%j.out

set -euo pipefail
SHARD="${SHARD:?submit with --export=ALL,SHARD=0..7}"

python3 -u <<'PY'
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
SHARD = int(os.environ["SHARD"])
if SHARD not in range(8):
    raise SystemExit("SHARD must be 0..7")

CODEQL = Path("/home-mscluster/astrauss/tools/codeql/codeql")
SEALED_TARS = [
    ROOT / f"T2_FINAL4_MATERIALIZE_SEALED_v1_S{i}.tar.gz"
    for i in range(4)
]
OUT = ROOT / f"T2_FINAL4_CODEQL_BLIND_v1_S{SHARD}"
PUBLIC = ROOT / f"T2_FINAL4_CODEQL_PUBLIC_v1_S{SHARD}.json"
SEALED_OUT = ROOT / f"T2_FINAL4_CODEQL_SEALED_v1_S{SHARD}.tar.gz"
TMP = Path(os.environ.get("SLURM_TMPDIR") or tempfile.mkdtemp(prefix=f"t2ql-s{SHARD}-"))

OUT.mkdir(parents=True, exist_ok=True)
SEALED_DIR = OUT / "SEALED"
SEALED_DIR.mkdir(exist_ok=True)

for p in [CODEQL, *SEALED_TARS]:
    if not p.exists():
        raise SystemExit(f"MISSING_REQUIRED_INPUT={p}")

def run(cmd, cwd=None, timeout=1800, env=None):
    return subprocess.run(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, env=env,
    )

def must(cmd, cwd=None, timeout=1800, env=None):
    p = run(cmd, cwd=cwd, timeout=timeout, env=env)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed rc={p.returncode}: {cmd}\n"
            f"stdout_tail={p.stdout[-1500:]}\n"
            f"stderr_tail={p.stderr[-2500:]}"
        )
    return p

def norm_path(s):
    p = str(s or "").replace("\\", "/").lstrip("./")
    if p.startswith("a/") or p.startswith("b/"):
        p = p[2:]
    return p

def sha256_text(s):
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()

def parse_added_lines(diff_text):
    out = defaultdict(set)
    current = None
    new_line = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = norm_path(line[6:])
            continue
        if line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,\d+)?", line)
            new_line = int(m.group(1)) if m else None
            continue
        if current is None or new_line is None:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            out[current].add(new_line)
            new_line += 1
        elif line.startswith("-"):
            continue
        else:
            new_line += 1
    return out

def result_locations(res):
    locs = []
    for loc in res.get("locations") or []:
        phys = loc.get("physicalLocation") or {}
        uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
        line = (phys.get("region") or {}).get("startLine")
        if uri:
            locs.append((uri, int(line) if line is not None else None))
    for loc in res.get("relatedLocations") or []:
        phys = loc.get("physicalLocation") or {}
        uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
        line = (phys.get("region") or {}).get("startLine")
        if uri:
            locs.append((uri, int(line) if line is not None else None))
    for flow in res.get("codeFlows") or []:
        for tf in flow.get("threadFlows") or []:
            for wrap in tf.get("locations") or []:
                loc = wrap.get("location") or {}
                phys = loc.get("physicalLocation") or {}
                uri = norm_path((phys.get("artifactLocation") or {}).get("uri"))
                line = (phys.get("region") or {}).get("startLine")
                if uri:
                    locs.append((uri, int(line) if line is not None else None))
    return locs

def parse_sarif(path):
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    findings = []
    for srun in data.get("runs", []) or []:
        for res in srun.get("results", []) or []:
            locs = result_locations(res)
            primary = locs[0] if locs else ("", None)
            msg = (res.get("message") or {}).get("text") or ""
            partial = res.get("partialFingerprints") or {}
            findings.append({
                "rule": str(res.get("ruleId") or ""),
                "file": primary[0],
                "line": primary[1],
                "message": msg,
                "locations": locs,
                "fingerprints": partial,
            })
    return findings

def finding_key(f):
    fps = f.get("fingerprints") or {}
    if fps:
        return (
            f.get("rule"),
            norm_path(f.get("file")),
            tuple(sorted((str(k), str(v)) for k, v in fps.items())),
        )
    return (
        f.get("rule"),
        norm_path(f.get("file")),
        re.sub(r"\s+", " ", str(f.get("message") or "")).strip(),
    )

def touches_added(f, added):
    for file, line in f.get("locations") or []:
        if line is not None and line in added.get(norm_path(file), set()):
            return True
    file = norm_path(f.get("file"))
    line = f.get("line")
    return line is not None and line in added.get(file, set())

def codeql_scan(src, label):
    dbdir = TMP / f"db_{label}"
    sarif = TMP / f"{label}.sarif"
    env = os.environ.copy()
    env["TMPDIR"] = str(TMP)

    create = run([
        str(CODEQL), "database", "create", str(dbdir),
        "--language=javascript-typescript",
        f"--source-root={src}",
        "--build-mode=none",
        "--ram=6000",
        "--threads=4",
    ], timeout=1800, env=env)
    if create.returncode != 0:
        return None, {
            "stage": "create",
            "rc": create.returncode,
            "stderr_tail": create.stderr[-2500:],
        }

    analyze = run([
        str(CODEQL), "database", "analyze", str(dbdir),
        "codeql/javascript-queries:codeql-suites/javascript-security-and-quality.qls",
        "--format=sarif-latest",
        f"--output={sarif}",
        "--ram=6000",
        "--threads=4",
    ], timeout=1800, env=env)
    if analyze.returncode != 0:
        return None, {
            "stage": "analyze",
            "rc": analyze.returncode,
            "stderr_tail": analyze.stderr[-2500:],
        }

    findings = parse_sarif(sarif)
    return findings, {"stage": "ok", "sarif": sarif}

# Load all 32 sealed materializations.
runs = {}
for tar_path in SEALED_TARS:
    with tarfile.open(tar_path, "r:gz") as tf:
        run_ids = sorted({
            m.name.split("/")[1]
            for m in tf.getmembers()
            if m.isfile() and re.match(r"^SEALED/RUN_\d{3}/", m.name)
        })
        for run_id in run_ids:
            meta_m = tf.getmember(f"SEALED/{run_id}/sealed_meta.json")
            diff_m = tf.getmember(f"SEALED/{run_id}/synthetic_pr.diff")
            meta = json.loads(tf.extractfile(meta_m).read().decode("utf-8"))
            diff = tf.extractfile(diff_m).read().decode("utf-8", errors="ignore")
            runs[run_id] = {"meta": meta, "diff": diff}

if len(runs) != 32:
    raise SystemExit(f"EXPECTED_32_RUNS_GOT={len(runs)}")

# There should be eight unique historical task states, four runs each.
groups = defaultdict(list)
for run_id, obj in runs.items():
    meta = obj["meta"]
    target_rules = tuple(sorted(str(x) for x in meta.get("target_rules") or []))
    key = (
        str(meta["repository"]),
        str(meta["base_sha"]),
        str(meta["head_sha"]),
        target_rules,
    )
    groups[key].append(run_id)

group_items = sorted(
    groups.items(),
    key=lambda kv: sha256_text("|".join([kv[0][0], kv[0][1], ",".join(kv[0][3])])),
)
if len(group_items) != 8:
    raise SystemExit(f"EXPECTED_8_TASK_STATES_GOT={len(group_items)}")
for _, ids in group_items:
    if len(ids) != 4:
        raise SystemExit(f"EXPECTED_4_RUNS_PER_TASK_STATE_GOT={len(ids)}")

(group_key, shard_runs) = group_items[SHARD]
repo_name, base_sha, head_sha, target_rules = group_key
shard_runs = sorted(shard_runs)

repo = TMP / "repo"
must(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", f"https://github.com/{repo_name}.git", str(repo)], timeout=900)
must(["git", "fetch", "-q", "origin", base_sha], cwd=repo, timeout=900)

def add_worktree(name):
    wt = TMP / name
    must(["git", "worktree", "add", "-q", "--detach", str(wt), base_sha], cwd=repo, timeout=300)
    return wt

baseline_wt = add_worktree("baseline")
base_findings, base_meta = codeql_scan(baseline_wt, "baseline")
if base_findings is None:
    raise RuntimeError(f"baseline CodeQL failed: {base_meta}")

base_keys = {finding_key(f) for f in base_findings}
public_rows = []

for run_id in shard_runs:
    diff = runs[run_id]["diff"]
    row = {
        "run_id": run_id,
        "scanner_valid": False,
        "scanner_positive": None,
        "target_finding_count": None,
        "status": "PENDING",
    }
    sealed_run = SEALED_DIR / run_id
    sealed_run.mkdir()

    try:
        # No code change => cannot introduce a new static finding.
        if not diff.strip():
            row.update({
                "scanner_valid": True,
                "scanner_positive": False,
                "target_finding_count": 0,
                "status": "NO_CHANGE",
            })
            public_rows.append(row)
            print(run_id, "scanner_valid=1 scanner_positive=False target_count=0 status=NO_CHANGE", flush=True)
            continue

        wt = add_worktree(run_id)
        patch_file = TMP / f"{run_id}.patch"
        patch_file.write_text(diff, encoding="utf-8")
        apply = run(["git", "apply", "--index", "--whitespace=nowarn", str(patch_file)], cwd=wt, timeout=300)
        if apply.returncode != 0:
            raise RuntimeError(f"git apply failed: {apply.stderr[-1800:]}")

        diff0 = must(["git", "diff", "--cached", "-U0", "--no-color", "--"], cwd=wt, timeout=300).stdout
        added = parse_added_lines(diff0)

        head_findings, head_meta = codeql_scan(wt, run_id)
        if head_findings is None:
            row["status"] = f"ERROR_{head_meta['stage'].upper()}"
            (sealed_run / "ERROR.json").write_text(json.dumps(head_meta, indent=2) + "\n")
            public_rows.append(row)
            print(run_id, f"scanner_valid=0 status={row['status']}", flush=True)
            continue

        introduced = [f for f in head_findings if finding_key(f) not in base_keys]
        linked = [f for f in introduced if touches_added(f, added)]
        target = [f for f in linked if f.get("rule") in set(target_rules)]

        row.update({
            "scanner_valid": True,
            "scanner_positive": bool(target),
            "target_finding_count": len(target),
            "status": "OK",
        })

        # Security-sensitive details stay sealed.
        (sealed_run / "counts_internal.json").write_text(json.dumps({
            "baseline_findings": len(base_findings),
            "head_findings": len(head_findings),
            "introduced_findings": len(introduced),
            "diff_linked_findings": len(linked),
            "target_count": len(target),
        }, indent=2) + "\n")
        if target:
            (sealed_run / "target_findings_internal.json").write_text(
                json.dumps(target, indent=2, ensure_ascii=False) + "\n"
            )

        print(
            run_id,
            f"scanner_valid=1 scanner_positive={row['scanner_positive']} "
            f"target_count={row['target_finding_count']} status=OK",
            flush=True,
        )

    except Exception as exc:
        row["status"] = "EVALUATION_ERROR"
        (sealed_run / "ERROR.txt").write_text(str(exc) + "\n", encoding="utf-8")
        public_rows.append(row)
        print(run_id, "scanner_valid=0 status=EVALUATION_ERROR", flush=True)
        continue

    public_rows.append(row)

public = {
    "version": "T2_FINAL4_CODEQL_BLIND_v1",
    "shard": SHARD,
    "run_ids": shard_runs,
    "run_count": len(shard_runs),
    "scanner_valid_count": sum(bool(r["scanner_valid"]) for r in public_rows),
    "scanner_positive_count": sum(r["scanner_positive"] is True for r in public_rows),
    "scanner_negative_count": sum(r["scanner_positive"] is False for r in public_rows),
    "notes": [
        "No P/N/+/- condition mapping is emitted or used.",
        "Repository names, target rule IDs, paths, and finding details remain sealed.",
        "Scanner positivity means a target-rule finding introduced relative to the exact pre-change baseline and linked to an added line/data-flow location."
    ],
}
PUBLIC.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")

if SEALED_OUT.exists():
    SEALED_OUT.unlink()
with tarfile.open(SEALED_OUT, "w:gz") as tf:
    tf.add(SEALED_DIR, arcname="SEALED")

print("STATUS=DONE")
print("SHARD=", SHARD)
print("RUNS=", len(shard_runs))
print("SCANNER_VALID=", public["scanner_valid_count"])
print("SCANNER_POSITIVE=", public["scanner_positive_count"])
print("SCANNER_NEGATIVE=", public["scanner_negative_count"])
print("PUBLIC=", PUBLIC)
print("SEALED_ON_CLUSTER=", SEALED_OUT)
PY
