#!/bin/bash
#SBATCH --job-name=t2func
#SBATCH --time=08:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_FUNCTIONAL_BLIND_v1_%j.out

set -euo pipefail

SHARD="${SHARD:?SHARD required}"

python3 -u <<'PY'
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tarfile
import time
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
SHARD = int(os.environ["SHARD"])

if SHARD not in range(8):
    raise SystemExit("SHARD must be 0..7")

FREEZE = (
    ROOT /
    "T2_FINAL4_FUNCTIONAL_GATE_FREEZE_SEALED_v1.json"
)

MATERIALIZED = [
    ROOT /
    f"T2_FINAL4_MATERIALIZE_SEALED_v1_S{i}.tar.gz"
    for i in range(4)
]

WORKROOT = (
    ROOT /
    "T2_FINAL4_FUNC_WORK" /
    str(os.environ.get("SLURM_JOB_ID", "manual"))
)

PUBLIC = (
    ROOT /
    f"T2_FINAL4_FUNCTIONAL_PUBLIC_v1_S{SHARD}.json"
)

SEALED_OUT = (
    ROOT /
    f"T2_FINAL4_FUNCTIONAL_SEALED_v1_S{SHARD}.tar.gz"
)

WORKROOT.mkdir(parents=True, exist_ok=True)

specs = json.loads(FREEZE.read_text())
spec = next(x for x in specs if x["shard"] == SHARD)

repo_name = spec["repository"]
base_sha = spec["base_sha"]
head_sha = spec["head_sha"]
run_ids = spec["run_ids"]

def run(
    cmd,
    cwd=None,
    timeout=2400,
    env=None,
):
    try:
        return subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        class R:
            returncode = 124
            stdout = e.stdout or ""
            stderr = e.stderr or "TIMEOUT"
        return R()

def must(cmd, cwd=None, timeout=1200):
    p = run(cmd, cwd=cwd, timeout=timeout)

    if p.returncode != 0:
        raise RuntimeError(
            f"command failed rc={p.returncode}: {cmd}\n"
            f"{p.stderr[-1500:]}"
        )

    return p

def find_pm_command(pm):
    if pm == "npm":
        p = shutil.which("npm")
        return [p] if p else None

    if pm == "pnpm":
        p = shutil.which("pnpm")
        if p:
            return [p]

        corepack = shutil.which("corepack")
        if corepack:
            return [corepack, "pnpm"]

    if pm == "bun":
        p = shutil.which("bun")

        if not p:
            candidate = (
                Path.home() /
                ".bun" /
                "bin" /
                "bun"
            )

            if candidate.exists():
                p = str(candidate)

        return [p] if p else None

    return None

def lock_root(repo, package_root, pm):
    cur = (repo / package_root).resolve()
    repo_root = repo.resolve()

    names = {
        "npm": [
            "package-lock.json",
            "npm-shrinkwrap.json",
        ],
        "pnpm": ["pnpm-lock.yaml"],
        "bun": [
            "bun.lock",
            "bun.lockb",
        ],
    }.get(pm, [])

    while True:
        if any(
            (cur / n).is_file()
            for n in names
        ):
            return cur

        if cur == repo_root:
            break

        cur = cur.parent

    return repo / package_root

def install(repo, gate, logdir):
    pm = gate["package_manager"]
    pmcmd = find_pm_command(pm)

    if not pmcmd:
        return 127, "PACKAGE_MANAGER_NOT_FOUND"

    root = lock_root(
        repo,
        gate["package_root"],
        pm
    )

    if pm == "npm":
        if (
            (root / "package-lock.json").exists()
            or
            (root / "npm-shrinkwrap.json").exists()
        ):
            cmd = pmcmd + ["ci"]
        else:
            cmd = pmcmd + ["install"]

    elif pm == "pnpm":
        cmd = pmcmd + [
            "install",
            "--frozen-lockfile",
        ]

    elif pm == "bun":
        cmd = pmcmd + [
            "install",
            "--frozen-lockfile",
        ]

    else:
        return 127, "UNKNOWN_PACKAGE_MANAGER"

    env = os.environ.copy()
    env["CI"] = "1"
    env["npm_config_audit"] = "false"
    env["npm_config_fund"] = "false"

    p = run(
        cmd,
        cwd=root,
        timeout=2400,
        env=env
    )

    (logdir / "install.stdout").write_text(
        p.stdout or "",
        errors="ignore"
    )

    (logdir / "install.stderr").write_text(
        p.stderr or "",
        errors="ignore"
    )

    return p.returncode, "OK" if p.returncode == 0 else "INSTALL_FAIL"

def run_gate(repo, gate, logdir, idx):
    pm = gate["package_manager"]
    pmcmd = find_pm_command(pm)

    if not pmcmd:
        return 127

    root = repo / gate["package_root"]

    cmd = pmcmd + [
        "run",
        gate["script"],
    ]

    env = os.environ.copy()
    env["CI"] = "1"

    p = run(
        cmd,
        cwd=root,
        timeout=2400,
        env=env
    )

    (logdir / f"gate_{idx}.stdout").write_text(
        p.stdout or "",
        errors="ignore"
    )

    (logdir / f"gate_{idx}.stderr").write_text(
        p.stderr or "",
        errors="ignore"
    )

    return p.returncode

def inject_oracle(repo):
    for rel in spec["oracle_files"]:
        target = repo / rel
        probe = run(
            [
                "git",
                "cat-file",
                "-e",
                f"{head_sha}:{rel}",
            ],
            cwd=repo,
            timeout=300
        )

        if probe.returncode == 0:
            target.parent.mkdir(
                parents=True,
                exist_ok=True
            )

            blob = subprocess.run(
                [
                    "git",
                    "show",
                    f"{head_sha}:{rel}",
                ],
                cwd=repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300
            )

            if blob.returncode != 0:
                raise RuntimeError(
                    "oracle extraction failed"
                )

            target.write_bytes(blob.stdout)

        else:
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()

def eval_state(repo, label, sealed_dir):
    logdir = sealed_dir / label
    logdir.mkdir(
        parents=True,
        exist_ok=True
    )

    install_codes = []

    seen_install_roots = set()

    for gate in spec["gates"]:
        key = (
            gate["package_manager"],
            str(
                lock_root(
                    repo,
                    gate["package_root"],
                    gate["package_manager"]
                )
            )
        )

        if key in seen_install_roots:
            continue

        seen_install_roots.add(key)

        code, status = install(
            repo,
            gate,
            logdir
        )

        install_codes.append(code)

        if code != 0:
            return {
                "setup_ok": False,
                "gate_ok": False,
                "gate_codes": [],
                "status": status,
            }

    gate_codes = []

    for idx, gate in enumerate(spec["gates"]):
        code = run_gate(
            repo,
            gate,
            logdir,
            idx
        )
        gate_codes.append(code)

    return {
        "setup_ok": True,
        "gate_ok": all(
            x == 0
            for x in gate_codes
        ),
        "gate_codes": gate_codes,
        "status": "OK",
    }

# Load generated diffs.
diffs = {}

for tar_path in MATERIALIZED:
    with tarfile.open(tar_path, "r:gz") as tf:
        for run_id in run_ids:
            name = (
                f"SEALED/{run_id}/synthetic_pr.diff"
            )

            try:
                member = tf.getmember(name)
            except KeyError:
                continue

            diffs[run_id] = (
                tf.extractfile(member)
                .read()
                .decode(
                    "utf-8",
                    errors="ignore"
                )
            )

if set(diffs) != set(run_ids):
    raise RuntimeError(
        f"missing generated diffs: "
        f"{set(run_ids)-set(diffs)}"
    )

repo = WORKROOT / "repo"

must([
    "git",
    "clone",
    "-q",
    "--filter=blob:none",
    "--no-checkout",
    f"https://github.com/{repo_name}.git",
    str(repo),
], timeout=1200)

must([
    "git",
    "fetch",
    "-q",
    "origin",
    base_sha,
    head_sha,
], cwd=repo, timeout=1200)

sealed_dir = WORKROOT / "sealed_logs"
sealed_dir.mkdir()

def make_worktree(name):
    wt = WORKROOT / name

    must([
        "git",
        "worktree",
        "add",
        "-q",
        "--detach",
        str(wt),
        base_sha,
    ], cwd=repo)

    return wt

# Baseline with historical regression oracle only.
base = make_worktree("baseline")
inject_oracle(base)

baseline = eval_state(
    base,
    "BASELINE",
    sealed_dir
)

print(
    "BASELINE",
    f"setup={baseline['setup_ok']}",
    f"gate={baseline['gate_ok']}",
    f"status={baseline['status']}",
    flush=True,
)

rows = []

for run_id in sorted(run_ids):
    wt = make_worktree(run_id)

    diff = diffs[run_id]

    if diff.strip():
        patch = (
            WORKROOT /
            f"{run_id}.patch"
        )

        patch.write_text(
            diff,
            encoding="utf-8"
        )

        p = run(
            [
                "git",
                "apply",
                "--whitespace=nowarn",
                str(patch),
            ],
            cwd=wt,
            timeout=300
        )

        if p.returncode != 0:
            result = {
                "setup_ok": False,
                "gate_ok": False,
                "status": "PATCH_APPLY_FAIL",
            }

            functional = "INVALID_PATCH"

            rows.append({
                "run_id": run_id,
                "generated": result,
                "functional_status": functional,
            })

            print(
                run_id,
                "FUNCTIONAL=INVALID_PATCH",
                flush=True,
            )

            continue

    inject_oracle(wt)

    result = eval_state(
        wt,
        run_id,
        sealed_dir
    )

    if not result["setup_ok"]:
        functional = "SETUP_FAIL"

    elif baseline["setup_ok"] and baseline["gate_ok"]:
        functional = (
            "PASS"
            if result["gate_ok"]
            else "FAIL"
        )

    elif (
        baseline["setup_ok"]
        and not baseline["gate_ok"]
        and result["gate_ok"]
    ):
        functional = "RECOVERED"

    elif (
        baseline["setup_ok"]
        and not baseline["gate_ok"]
        and not result["gate_ok"]
    ):
        functional = "BASELINE_NOISY"

    else:
        functional = "BASELINE_SETUP_FAIL"

    rows.append({
        "run_id": run_id,
        "generated": result,
        "functional_status": functional,
    })

    print(
        run_id,
        f"setup={result['setup_ok']}",
        f"gate={result['gate_ok']}",
        f"FUNCTIONAL={functional}",
        flush=True,
    )

public = {
    "version": "T2_FINAL4_FUNCTIONAL_BLIND_v1",
    "shard": SHARD,
    "run_count": len(rows),
    "baseline": {
        "setup_ok": baseline["setup_ok"],
        "gate_ok": baseline["gate_ok"],
        "status": baseline["status"],
    },
    "runs": [
        {
            "run_id": x["run_id"],
            "setup_ok": x["generated"]["setup_ok"],
            "gate_ok": x["generated"]["gate_ok"],
            "functional_status": x[
                "functional_status"
            ],
        }
        for x in rows
    ],
    "condition_mapping_used": False,
    "scanner_outcomes_used": False,
}

PUBLIC.write_text(
    json.dumps(public, indent=2) + "\n"
)

if SEALED_OUT.exists():
    SEALED_OUT.unlink()

with tarfile.open(
    SEALED_OUT,
    "w:gz"
) as tf:
    tf.add(
        sealed_dir,
        arcname="SEALED_LOGS"
    )

print("STATUS=DONE")
print("SHARD=", SHARD)
print("RUNS=", len(rows))

from collections import Counter

counts = Counter(
    x["functional_status"]
    for x in rows
)

print(
    "FUNCTIONAL_COUNTS=",
    json.dumps(
        dict(sorted(counts.items()))
    )
)

print("PUBLIC=", PUBLIC)
print("SEALED=", SEALED_OUT)

# Keep final artifacts, remove huge worktrees.
for child in list(WORKROOT.iterdir()):
    if child.name == "sealed_logs":
        continue

try:
    shutil.rmtree(WORKROOT)
except Exception:
    pass
PY
