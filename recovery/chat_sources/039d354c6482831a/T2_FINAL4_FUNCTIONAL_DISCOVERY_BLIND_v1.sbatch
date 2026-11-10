#!/bin/bash
#SBATCH --job-name=t2funcdisc
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_FUNC_DISCOVERY_v1_%j.out

set -euo pipefail
SHARD="${SHARD:?submit with --export=ALL,SHARD=0..7}"

python3 -u <<'PY'
from __future__ import annotations

import json
import os
import re
import subprocess
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
SHARD = int(os.environ["SHARD"])
if SHARD not in range(8):
    raise SystemExit("SHARD must be 0..7")

SEALED_TARS = [
    ROOT / f"T2_FINAL4_MATERIALIZE_SEALED_v1_S{i}.tar.gz"
    for i in range(4)
]
PUBLIC = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_PUBLIC_v1_S{SHARD}.json"
SEALED_JSON = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_SEALED_v1_S{SHARD}.json"
SEALED_TAR = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_SEALED_v1_S{SHARD}.tar.gz"
TMP = Path(os.environ.get("SLURM_TMPDIR") or tempfile.mkdtemp(prefix=f"t2fd-s{SHARD}-"))

for p in SEALED_TARS:
    if not p.exists():
        raise SystemExit("MISSING_SEALED_MATERIALIZATION")

def run(cmd, cwd=None, timeout=900):
    return subprocess.run(
        cmd, cwd=cwd, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout
    )

def must(cmd, cwd=None, timeout=900):
    p = run(cmd, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"command failed rc={p.returncode}")
    return p

def test_like(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return bool(
        re.search(r"(^|/)(__tests__|tests?|specs?|e2e|integration)(/|$)", p)
        or re.search(r"\.(test|spec)\.[a-z0-9]+$", p)
    )

def config_or_fixture(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return bool(
        re.search(r"(^|/)(fixtures?|testdata|mocks?|snapshots?)(/|$)", p)
        or p.endswith((
            ".snap", "vitest.config.ts", "vitest.config.js",
            "jest.config.js", "jest.config.ts",
            "playwright.config.ts", "playwright.config.js"
        ))
    )

def nearest_package_root(repo: Path, relpath: str) -> str | None:
    cur = (repo / relpath).parent
    root = repo.resolve()
    while True:
        if (cur / "package.json").is_file():
            return str(cur.resolve().relative_to(root))
        if cur.resolve() == root:
            break
        cur = cur.parent
    if (repo / "package.json").is_file():
        return "."
    return None

def detect_pm(repo: Path, package_root: str | None):
    starts = []
    if package_root is not None:
        starts.append(repo / package_root)
    starts.append(repo)
    seen = set()
    for start in starts:
        cur = start.resolve()
        root = repo.resolve()
        while True:
            if cur in seen:
                pass
            else:
                seen.add(cur)
                if (cur / "pnpm-lock.yaml").is_file():
                    return "pnpm", str(cur.relative_to(root) or ".")
                if (cur / "yarn.lock").is_file():
                    return "yarn", str(cur.relative_to(root) or ".")
                if (cur / "bun.lockb").is_file() or (cur / "bun.lock").is_file():
                    return "bun", str(cur.relative_to(root) or ".")
                if (cur / "package-lock.json").is_file() or (cur / "npm-shrinkwrap.json").is_file():
                    return "npm", str(cur.relative_to(root) or ".")
            if cur == root:
                break
            cur = cur.parent
    return ("npm", package_root or ".")

def package_scripts(repo: Path, package_root: str | None):
    if package_root is None:
        return {}
    p = repo / package_root / "package.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        scripts = data.get("scripts") or {}
        return {str(k): str(v) for k, v in scripts.items() if isinstance(v, str)}
    except Exception:
        return {}

# Load all sealed run metadata and group into the same 8 historical task states
# used for the scanner stage.
runs = {}
for tar_path in SEALED_TARS:
    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if not (m.isfile() and m.name.endswith("/sealed_meta.json")):
                continue
            parts = Path(m.name).parts
            run_id = next((x for x in parts if re.fullmatch(r"RUN_\d{3}", x)), None)
            if not run_id:
                continue
            meta = json.loads(tf.extractfile(m).read().decode("utf-8"))
            runs[run_id] = meta

if len(runs) != 32:
    raise SystemExit(f"EXPECTED_32_RUNS_GOT={len(runs)}")

groups = defaultdict(list)
for run_id, meta in runs.items():
    key = (
        str(meta["repository"]),
        str(meta["base_sha"]),
        str(meta["head_sha"]),
        tuple(sorted(str(x) for x in (meta.get("target_rules") or []))),
    )
    groups[key].append(run_id)

group_items = sorted(
    groups.items(),
    key=lambda kv: "|".join([kv[0][0], kv[0][1], ",".join(kv[0][3])])
)
if len(group_items) != 8:
    raise SystemExit(f"EXPECTED_8_TASK_STATES_GOT={len(group_items)}")

(group_key, run_ids) = group_items[SHARD]
repo_name, base_sha, head_sha, target_rules = group_key

repo = TMP / "repo"
try:
    must(["git", "clone", "-q", "--filter=blob:none", "--no-checkout",
          f"https://github.com/{repo_name}.git", str(repo)], timeout=900)
    must(["git", "fetch", "-q", "origin", base_sha, head_sha], cwd=repo, timeout=900)
    must(["git", "checkout", "-q", "--detach", base_sha], cwd=repo, timeout=300)

    diff = must(
        ["git", "diff", "--name-status", "--find-renames", base_sha, head_sha, "--"],
        cwd=repo, timeout=300
    ).stdout

    changed = []
    for line in diff.splitlines():
        if not line.strip():
            continue
        cols = line.split("\t")
        status = cols[0]
        path = cols[-1]
        changed.append({"status": status, "path": path})

    test_files = [x["path"] for x in changed if test_like(x["path"])]
    fixture_files = [x["path"] for x in changed if config_or_fixture(x["path"])]
    source_files = [
        x["path"] for x in changed
        if x["path"] not in set(test_files) and x["path"] not in set(fixture_files)
    ]

    roots = sorted({
        r for p in changed
        if (r := nearest_package_root(repo, p["path"])) is not None
    })
    if not roots and (repo / "package.json").is_file():
        roots = ["."]

    root_info = []
    for pr in roots:
        scripts = package_scripts(repo, pr)
        pm, lock_root = detect_pm(repo, pr)
        interesting = {}
        for name in ["test", "test:unit", "test:ci", "typecheck", "type-check",
                     "check", "build", "lint"]:
            if name in scripts:
                interesting[name] = scripts[name]
        root_info.append({
            "package_root": pr,
            "package_manager": pm,
            "lock_root": lock_root,
            "scripts": scripts,
            "interesting_scripts": interesting,
        })

    sealed = {
        "version": "T2_FINAL4_FUNC_DISCOVERY_SEALED_v1",
        "shard": SHARD,
        "run_ids": sorted(run_ids),
        "repository": repo_name,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "target_rules": list(target_rules),
        "historical_changed_files": changed,
        "historical_test_files": test_files,
        "historical_fixture_files": fixture_files,
        "historical_source_files": source_files,
        "package_roots": root_info,
    }
    SEALED_JSON.write_text(json.dumps(sealed, indent=2) + "\n", encoding="utf-8")

    public = {
        "version": "T2_FINAL4_FUNC_DISCOVERY_PUBLIC_v1",
        "shard": SHARD,
        "run_count": len(run_ids),
        "historical_changed_file_count": len(changed),
        "historical_test_file_count": len(test_files),
        "historical_fixture_file_count": len(fixture_files),
        "package_root_count": len(roots),
        "package_managers": sorted({x["package_manager"] for x in root_info}),
        "available_gate_families": {
            "test": any(any(k.startswith("test") for k in x["scripts"]) for x in root_info),
            "typecheck": any(any(k in x["scripts"] for k in ["typecheck","type-check"]) for x in root_info),
            "check": any("check" in x["scripts"] for x in root_info),
            "build": any("build" in x["scripts"] for x in root_info),
            "lint": any("lint" in x["scripts"] for x in root_info),
        },
        "status": "OK",
        "notes": [
            "No condition labels or scanner outcomes were used.",
            "Repository names, real paths, commits, target rules, and script bodies remain sealed.",
            "This stage discovers candidate functional oracles before generated-state functional outcomes are run."
        ],
    }
    PUBLIC.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")

    if SEALED_TAR.exists():
        SEALED_TAR.unlink()
    with tarfile.open(SEALED_TAR, "w:gz") as tf:
        tf.add(SEALED_JSON, arcname=SEALED_JSON.name)

    print("STATUS=DONE")
    print("SHARD=", SHARD)
    print("RUNS=", len(run_ids))
    print("HIST_CHANGED=", len(changed))
    print("HIST_TEST_FILES=", len(test_files))
    print("HIST_FIXTURE_FILES=", len(fixture_files))
    print("PACKAGE_ROOTS=", len(roots))
    print("PACKAGE_MANAGERS=", ",".join(public["package_managers"]) or "none")
    print("GATES=", json.dumps(public["available_gate_families"], sort_keys=True))
    print("PUBLIC=", PUBLIC)
    print("SEALED=", SEALED_TAR)

except Exception as exc:
    PUBLIC.write_text(json.dumps({
        "version": "T2_FINAL4_FUNC_DISCOVERY_PUBLIC_v1",
        "shard": SHARD,
        "status": "ERROR",
        "error_type": type(exc).__name__,
    }, indent=2) + "\n")
    print("STATUS=ERROR")
    print("SHARD=", SHARD)
    print("ERROR_TYPE=", type(exc).__name__)
    raise
PY
