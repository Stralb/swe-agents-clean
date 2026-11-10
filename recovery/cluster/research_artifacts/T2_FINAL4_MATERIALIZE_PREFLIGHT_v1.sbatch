#!/bin/bash
#SBATCH --job-name=t2mat4
#SBATCH --partition=batch
#SBATCH --time=00:12:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=/home-mscluster/astrauss/research_artifacts/T2_FINAL4_MATERIALIZE_v1_%j.out

set -euo pipefail
SHARD="${SHARD:?submit with --export=ALL,SHARD=0..3}"

python3 -u <<'PY'
from __future__ import annotations

import collections
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path.home() / "research_artifacts"
SHARD = int(os.environ["SHARD"])
if SHARD not in range(4):
    raise SystemExit("SHARD must be 0..3")

GEN_BUNDLE = ROOT / "T2_FINAL4_GENERATIONS_FROZEN_v1.zip"
SEALED_PACKET = ROOT / f"T2_FINAL5_PACKET_BUILD_v2_S{SHARD}_SEALED.tar.gz"
RUN_PACKET_TAR = ROOT / f"T2_FINAL5_RUN_BUNDLES_v2_S{SHARD}.tar.gz"

EXPECTED_GEN_SHA = "541ab3e2d0d258bc9036e5b743b90cfccbfff8dd346150f2ccddb26c6436de7a"

OUT = ROOT / f"T2_FINAL4_MATERIALIZE_v1_S{SHARD}"
PUBLIC = ROOT / f"T2_FINAL4_MATERIALIZE_PUBLIC_v1_S{SHARD}.json"
SEALED_OUT = ROOT / f"T2_FINAL4_MATERIALIZE_SEALED_v1_S{SHARD}.tar.gz"
BLIND_REVIEW = ROOT / f"T2_FINAL4_BLIND_REVIEW_v1_S{SHARD}.tar.gz"

TMP = Path(os.environ.get("SLURM_TMPDIR") or tempfile.mkdtemp(prefix=f"t2mat4-s{SHARD}-"))

for p in (GEN_BUNDLE, SEALED_PACKET, RUN_PACKET_TAR):
    if not p.exists():
        raise SystemExit(f"MISSING_REQUIRED_INPUT={p}")

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

if sha256_file(GEN_BUNDLE) != EXPECTED_GEN_SHA:
    raise SystemExit("GENERATION_BUNDLE_HASH_MISMATCH")

def run(cmd, cwd=None, timeout=600):
    return subprocess.run(
        cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout
    )

def must(cmd, cwd=None, timeout=600):
    p = run(cmd, cwd=cwd, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(
            f"command failed rc={p.returncode}: {cmd}\n"
            f"stdout_tail={p.stdout[-1200:]}\n"
            f"stderr_tail={p.stderr[-1800:]}"
        )
    return p

def canonical_scanner(s: str) -> str:
    q = str(s or "").strip().lower().replace("_", "-")
    if q.startswith("codeql"):
        return "codeql"
    if q.startswith("semgrep"):
        return "semgrep"
    if q.startswith("gitleaks"):
        return "gitleaks"
    if q in {"osv", "osv-scanner", "osv-dependency"}:
        return "osv"
    if q.startswith("trivy"):
        return "trivy"
    if q in {"dependency-diff", "dependency-downgrade"}:
        return "dependency-diff"
    return q or "unknown"

def safe_rel(path: str) -> Path:
    p = Path(path)
    if not path or p.is_absolute() or ".." in p.parts:
        raise RuntimeError("unsafe mapped path")
    return p

# Load run map from the sealed packet builder artifact.
with tarfile.open(SEALED_PACKET, "r:gz") as tf:
    member = next(
        m for m in tf.getmembers()
        if m.isfile() and m.name.endswith("/RUN_MAP.json")
    )
    run_map = json.loads(tf.extractfile(member).read().decode("utf-8"))

if len(run_map) != 8:
    raise SystemExit(f"EXPECTED_8_RUNS_IN_SHARD_GOT={len(run_map)}")

# Load all frozen generations.
generations = {}
with zipfile.ZipFile(GEN_BUNDLE, "r") as outer:
    for run_id in run_map:
        name = f"{run_id}_OUTPUT.zip"
        if name not in outer.namelist():
            raise RuntimeError(f"missing frozen output for {run_id}")
        raw = outer.read(name)
        with zipfile.ZipFile(io.BytesIO(raw), "r") as inner:
            if set(inner.namelist()) != {"generation.json"}:
                raise RuntimeError(f"{run_id} output does not contain exactly generation.json")
            obj = json.loads(inner.read("generation.json").decode("utf-8"))
            if not isinstance(obj, dict) or not isinstance(obj.get("files"), list):
                raise RuntimeError(f"{run_id} invalid generation schema")
            generations[run_id] = obj

# Extract opaque run packets for blind review, but later omit ADDITIONAL_CONTEXT.txt.
packet_bytes = {}
with tarfile.open(RUN_PACKET_TAR, "r:gz") as tf:
    for m in tf.getmembers():
        if m.isfile() and re.fullmatch(r"RUN_\d{3}\.zip", Path(m.name).name):
            packet_bytes[Path(m.name).stem] = tf.extractfile(m).read()

if set(packet_bytes) != set(run_map):
    raise RuntimeError("run packet IDs do not match sealed run map")

# Group by exact repo/base so we only fetch each historical state once.
state_groups = collections.defaultdict(list)
for run_id, meta in run_map.items():
    key = (meta["actual_repository"], meta["base_sha"], meta["head_sha"])
    state_groups[key].append(run_id)

repo_roots = {}
for idx, ((repo_name, base_sha, head_sha), run_ids) in enumerate(sorted(state_groups.items()), 1):
    repo_dir = TMP / f"repo_{idx}"
    repo_dir.mkdir(parents=True)
    must(["git", "init", "-q"], cwd=repo_dir)
    must(["git", "remote", "add", "origin", f"https://github.com/{repo_name}.git"], cwd=repo_dir)
    must(["git", "fetch", "-q", "--filter=blob:none", "--no-tags", "origin", base_sha], cwd=repo_dir, timeout=900)
    # head is fetched only for provenance parity; materialization starts from base.
    p = run(["git", "fetch", "-q", "--filter=blob:none", "--no-tags", "origin", head_sha], cwd=repo_dir, timeout=900)
    repo_roots[(repo_name, base_sha, head_sha)] = repo_dir

sealed_dir = OUT / "SEALED"
blind_dir = OUT / "BLIND_REVIEW"
sealed_dir.mkdir(parents=True, exist_ok=True)
blind_dir.mkdir(parents=True, exist_ok=True)

public_rows = []
scanner_families = collections.Counter()

for run_id in sorted(run_map):
    meta = run_map[run_id]
    gen = generations[run_id]
    fams = sorted({canonical_scanner(x) for x in (meta.get("target_scanners") or [])})
    for fam in fams:
        scanner_families[fam] += 1

    summary = {
        "run_id": run_id,
        "materialized": False,
        "generation_file_entries": len(gen["files"]),
        "changed_file_count": None,
        "diff_nonempty": None,
        "diff_check_pass": None,
        "scanner_families": fams,
        "error_code": None,
    }

    run_sealed = sealed_dir / run_id
    run_sealed.mkdir()

    try:
        repo_key = (meta["actual_repository"], meta["base_sha"], meta["head_sha"])
        repo_dir = repo_roots[repo_key]
        wt = TMP / f"wt_{run_id}"
        must(["git", "worktree", "add", "-q", "--detach", str(wt), meta["base_sha"]], cwd=repo_dir)

        id_to_path = dict(meta["file_id_to_real_path"])
        seen_ids = set()

        for item in gen["files"]:
            if not isinstance(item, dict):
                raise RuntimeError("generation entry not object")
            file_id = str(item.get("file_id") or "")
            action = str(item.get("action") or "")
            if file_id not in id_to_path:
                raise RuntimeError("unknown file_id")
            if file_id in seen_ids:
                raise RuntimeError("duplicate file_id")
            seen_ids.add(file_id)

            rel = safe_rel(id_to_path[file_id])
            dst = wt / rel
            root = wt.resolve()
            resolved = dst.resolve(strict=False)
            if resolved != root and root not in resolved.parents:
                raise RuntimeError("mapped path escapes worktree")
            if dst.exists() and dst.is_symlink():
                raise RuntimeError("refusing symlink mutation")

            if action == "modify":
                if not dst.exists() or not dst.is_file():
                    raise RuntimeError("modify target missing")
                content = item.get("content")
                if not isinstance(content, str):
                    raise RuntimeError("modify missing string content")
                dst.write_text(content, encoding="utf-8")
            elif action == "create":
                if dst.exists():
                    raise RuntimeError("create target already exists")
                content = item.get("content")
                if not isinstance(content, str):
                    raise RuntimeError("create missing string content")
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(content, encoding="utf-8")
            elif action == "delete":
                if not dst.exists() or not dst.is_file():
                    raise RuntimeError("delete target missing")
                dst.unlink()
            else:
                raise RuntimeError("unsupported action")

        must(["git", "add", "-A", "--"], cwd=wt)
        diff = must(["git", "diff", "--cached", "--binary", "--no-ext-diff", "--"], cwd=wt).stdout
        status = must(["git", "status", "--porcelain"], cwd=wt).stdout
        changed = [line[3:] for line in status.splitlines() if len(line) >= 4]
        chk = run(["git", "diff", "--cached", "--check"], cwd=wt)

        (run_sealed / "synthetic_pr.diff").write_text(diff, encoding="utf-8")
        (run_sealed / "generation.json").write_text(
            json.dumps(gen, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (run_sealed / "sealed_meta.json").write_text(
            json.dumps({
                "repository": meta["actual_repository"],
                "base_sha": meta["base_sha"],
                "head_sha": meta["head_sha"],
                "file_id_to_real_path": id_to_path,
                "target_scanners": meta.get("target_scanners") or [],
                "target_rules": meta.get("target_rules") or [],
            }, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

        summary.update({
            "materialized": True,
            "changed_file_count": len(changed),
            "diff_nonempty": bool(diff.strip()),
            "diff_check_pass": chk.returncode == 0,
        })

        # Build a reviewer packet that remains blind to role and X exposure:
        # issue/base files + generation, but no ADDITIONAL_CONTEXT.txt and no real paths.
        review_run = blind_dir / run_id
        review_run.mkdir()
        with zipfile.ZipFile(io.BytesIO(packet_bytes[run_id]), "r") as pz:
            for name in pz.namelist():
                if name == "ADDITIONAL_CONTEXT.txt":
                    continue
                if name.endswith("/"):
                    continue
                if name in {"PROMPT.txt", "ISSUE.md", "FILES.json"} or name.startswith("FILES/"):
                    dst = review_run / name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_bytes(pz.read(name))
        (review_run / "generation.json").write_text(
            json.dumps(gen, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8"
        )

    except Exception as exc:
        summary["error_code"] = type(exc).__name__
        (run_sealed / "ERROR.txt").write_text(str(exc) + "\n", encoding="utf-8")

    public_rows.append(summary)
    print(
        run_id,
        f"materialized={int(bool(summary['materialized']))}",
        f"files={summary['generation_file_entries']}",
        f"changed={summary['changed_file_count']}",
        f"diff={summary['diff_nonempty']}",
        f"check={summary['diff_check_pass']}",
        f"scan={','.join(fams) if fams else 'none'}",
        f"error={summary['error_code'] or 'none'}",
        flush=True,
    )

public = {
    "version": "T2_FINAL4_MATERIALIZE_PUBLIC_v1",
    "shard": SHARD,
    "runs": public_rows,
    "run_count": len(public_rows),
    "materialized_count": sum(bool(x["materialized"]) for x in public_rows),
    "nonempty_diff_count": sum(bool(x["diff_nonempty"]) for x in public_rows if x["materialized"]),
    "scanner_family_run_counts": dict(sorted(scanner_families.items())),
    "generation_bundle_sha256": EXPECTED_GEN_SHA,
    "notes": [
        "No P/N/+/- condition labels are emitted.",
        "No scanner rule IDs, repository names, commit SHAs, or real file paths are emitted.",
        "Blind review packets omit ADDITIONAL_CONTEXT.txt so X exposure remains hidden from the reviewer."
    ]
}
PUBLIC.write_text(json.dumps(public, indent=2) + "\n", encoding="utf-8")

if SEALED_OUT.exists():
    SEALED_OUT.unlink()
with tarfile.open(SEALED_OUT, "w:gz") as tf:
    tf.add(sealed_dir, arcname="SEALED")

if BLIND_REVIEW.exists():
    BLIND_REVIEW.unlink()
with tarfile.open(BLIND_REVIEW, "w:gz") as tf:
    tf.add(blind_dir, arcname="BLIND_REVIEW")

print("STATUS=DONE")
print("SHARD=", SHARD)
print("RUNS=", public["run_count"])
print("MATERIALIZED=", public["materialized_count"])
print("NONEMPTY_DIFFS=", public["nonempty_diff_count"])
print("SCANNER_FAMILY_COUNTS=", json.dumps(public["scanner_family_run_counts"], sort_keys=True))
print("PUBLIC=", PUBLIC)
print("SEALED_ON_CLUSTER=", SEALED_OUT)
print("BLIND_REVIEW=", BLIND_REVIEW)
print("BLIND_REVIEW_SHA256=", sha256_file(BLIND_REVIEW))
PY
