#!/bin/bash
#SBATCH --job-name=t2funcdisc
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_FUNC_DISCOVERY_v1_%j.out

set -euo pipefail

SHARD="${SHARD:?SHARD required}"

python3 -u <<'PY'
from __future__ import annotations

import hashlib
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
TMP = Path(os.environ.get("SLURM_TMPDIR") or tempfile.mkdtemp(prefix="t2funcdisc-"))

if SHARD not in range(8):
    raise SystemExit("SHARD must be 0..7")

SEALED_TARS = [
    ROOT / f"T2_FINAL4_MATERIALIZE_SEALED_v1_S{i}.tar.gz"
    for i in range(4)
]

PUBLIC = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_PUBLIC_v1_S{SHARD}.json"
SEALED_JSON = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_SEALED_v1_S{SHARD}.json"
SEALED_TAR = ROOT / f"T2_FINAL4_FUNC_DISCOVERY_SEALED_v1_S{SHARD}.tar.gz"

def run(cmd, cwd=None, timeout=900):
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout
    )

def must(cmd, cwd=None, timeout=900):
    p = run(cmd, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed rc={p.returncode}\n"
            f"stderr_tail={p.stderr[-1500:]}"
        )
    return p

def is_test(path):
    p = path.replace("\\", "/").lower()
    return bool(
        re.search(r"(^|/)(__tests__|tests?|specs?|e2e|integration)(/|$)", p)
        or re.search(r"\.(test|spec)\.[a-z0-9]+$", p)
    )

def is_fixture(path):
    p = path.replace("\\", "/").lower()
    return bool(
        re.search(r"(^|/)(fixtures?|testdata|mocks?|snapshots?)(/|$)", p)
        or p.endswith(".snap")
    )

def package_root(repo, relpath):
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

def scripts_for(repo, root):
    if root is None:
        return {}

    p = repo / root / "package.json"

    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        scripts = obj.get("scripts") or {}
        return {
            str(k): str(v)
            for k, v in scripts.items()
            if isinstance(v, str)
        }
    except Exception:
        return {}

def package_manager(repo, root):
    start = (repo / root).resolve() if root else repo.resolve()
    repo_root = repo.resolve()
    cur = start

    while True:
        if (cur / "pnpm-lock.yaml").is_file():
            return "pnpm"
        if (cur / "yarn.lock").is_file():
            return "yarn"
        if (cur / "bun.lock").is_file() or (cur / "bun.lockb").is_file():
            return "bun"
        if (cur / "package-lock.json").is_file() or (cur / "npm-shrinkwrap.json").is_file():
            return "npm"

        if cur == repo_root:
            break

        cur = cur.parent

    return "npm"

runs = {}

for tar_path in SEALED_TARS:
    if not tar_path.exists():
        raise SystemExit(f"MISSING={tar_path}")

    with tarfile.open(tar_path, "r:gz") as tf:
        for m in tf.getmembers():
            if not (m.isfile() and m.name.endswith("/sealed_meta.json")):
                continue

            match = re.search(r"(RUN_\d{3})", m.name)

            if not match:
                continue

            run_id = match.group(1)
            runs[run_id] = json.loads(
                tf.extractfile(m).read().decode("utf-8")
            )

if len(runs) != 32:
    raise SystemExit(f"EXPECTED_32_RUNS_GOT={len(runs)}")

groups = defaultdict(list)

for run_id, meta in runs.items():
    key = (
        str(meta["repository"]),
        str(meta["base_sha"]),
        str(meta["head_sha"]),
        tuple(sorted(str(x) for x in (meta.get("target_rules") or [])))
    )
    groups[key].append(run_id)

if len(groups) != 8:
    raise SystemExit(f"EXPECTED_8_TASK_STATES_GOT={len(groups)}")

def group_hash(item):
    key = item[0]
    text = "|".join([
        key[0],
        key[1],
        ",".join(key[3])
    ])
    return hashlib.sha256(text.encode()).hexdigest()

group_items = sorted(groups.items(), key=group_hash)

(group_key, run_ids) = group_items[SHARD]

repo_name, base_sha, head_sha, target_rules = group_key

repo = TMP / "repo"

must([
    "git", "clone",
    "-q",
    "--filter=blob:none",
    "--no-checkout",
    f"https://github.com/{repo_name}.git",
    str(repo)
], timeout=900)

must([
    "git", "fetch",
    "-q",
    "origin",
    base_sha,
    head_sha
], cwd=repo, timeout=900)

must([
    "git", "checkout",
    "-q",
    "--detach",
    base_sha
], cwd=repo)

diff = must([
    "git", "diff",
    "--name-status",
    "--find-renames",
    base_sha,
    head_sha,
    "--"
], cwd=repo).stdout

changed = []

for line in diff.splitlines():
    if not line.strip():
        continue

    cols = line.split("\t")

    changed.append({
        "status": cols[0],
        "path": cols[-1]
    })

test_files = [
    x["path"]
    for x in changed
    if is_test(x["path"])
]

fixture_files = [
    x["path"]
    for x in changed
    if is_fixture(x["path"])
]

roots = sorted({
    r
    for x in changed
    if (r := package_root(repo, x["path"])) is not None
})

if not roots and (repo / "package.json").is_file():
    roots = ["."]

packages = []

for root in roots:
    scripts = scripts_for(repo, root)

    packages.append({
        "package_root": root,
        "package_manager": package_manager(repo, root),
        "scripts": scripts
    })

sealed = {
    "version": "T2_FINAL4_FUNC_DISCOVERY_SEALED_v1",
    "shard": SHARD,
    "run_ids": sorted(run_ids),
    "repository": repo_name,
    "base_sha": base_sha,
    "head_sha": head_sha,
    "target_rules": list(target_rules),
    "changed_files": changed,
    "test_files": test_files,
    "fixture_files": fixture_files,
    "packages": packages
}

SEALED_JSON.write_text(
    json.dumps(sealed, indent=2) + "\n",
    encoding="utf-8"
)

families = {
    "test": any(
        any(k == "test" or k.startswith("test:") for k in x["scripts"])
        for x in packages
    ),
    "typecheck": any(
        "typecheck" in x["scripts"] or "type-check" in x["scripts"]
        for x in packages
    ),
    "check": any(
        "check" in x["scripts"]
        for x in packages
    ),
    "build": any(
        "build" in x["scripts"]
        for x in packages
    ),
    "lint": any(
        "lint" in x["scripts"]
        for x in packages
    )
}

public = {
    "version": "T2_FINAL4_FUNC_DISCOVERY_PUBLIC_v1",
    "shard": SHARD,
    "run_count": len(run_ids),
    "historical_changed_file_count": len(changed),
    "historical_test_file_count": len(test_files),
    "historical_fixture_file_count": len(fixture_files),
    "package_root_count": len(roots),
    "package_managers": sorted({
        x["package_manager"]
        for x in packages
    }),
    "available_gate_families": families,
    "status": "OK"
}

PUBLIC.write_text(
    json.dumps(public, indent=2) + "\n",
    encoding="utf-8"
)

if SEALED_TAR.exists():
    SEALED_TAR.unlink()

with tarfile.open(SEALED_TAR, "w:gz") as tf:
    tf.add(
        SEALED_JSON,
        arcname=SEALED_JSON.name
    )

print("STATUS=DONE")
print("SHARD=", SHARD)
print("RUNS=", len(run_ids))
print("HIST_CHANGED=", len(changed))
print("HIST_TEST_FILES=", len(test_files))
print("HIST_FIXTURE_FILES=", len(fixture_files))
print("PACKAGE_ROOTS=", len(roots))
print(
    "PACKAGE_MANAGERS=",
    ",".join(public["package_managers"]) or "none"
)
print(
    "GATES=",
    json.dumps(families, sort_keys=True)
)
print("PUBLIC=", PUBLIC)
print("SEALED=", SEALED_TAR)
PY
